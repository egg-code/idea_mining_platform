import json
import os
import time
import logging
import requests
from sqlalchemy import text
from config.prompts import system_prompt
from config.queries import get_unprocessed_posts_query, insert_idea_query
from concurrent.futures import ThreadPoolExecutor, as_completed

"""
LLM Processor — Enriches Reddit posts with deep product-idea analysis via Ollama.

Reads from: staging.cleaned_reddit
Writes to:  staging.llm_outputs
"""


logger = logging.getLogger(__name__)

PROVIDER = os.getenv("LLM_PROVIDER", "cloud").lower()
# 2. Auto-configure based on the switch
if PROVIDER == "local":
    logger.info("Using LOCAL Ollama for processing.")
    LLM_API_URL = os.getenv("LOCAL_API_URL")
    LLM_MODEL = os.getenv("LOCAL_MODEL")
    API_KEY = "dummy_key"
    SLEEP_TIME = 0   # No limits locally
    TIMEOUT = 900    # Give weak CPUs 15 minutes
else:
    logger.info("Using CLOUD Groq for processing.")
    LLM_API_URL = os.getenv("GROQ_API_URL")
    LLM_MODEL = os.getenv("GROQ_MODEL")
    API_KEY = os.getenv("GROQ_API_KEY")
    SLEEP_TIME = 15  # Respect Groq rate limits
    TIMEOUT = 120    # Fast cloud timeout

SYSTEM_PROMPT = system_prompt # Details on config/prompts.py


# ============================================================
# Database queries
# ============================================================

def get_unprocessed_posts(engine, batch_size=50):
    """
    Finds posts in staging.cleaned_reddit that have not been
    processed yet (no matching row in staging.llm_output).
    """
    query = get_unprocessed_posts_query
    with engine.connect() as conn:
        result = conn.execute(query, {"batch_size": batch_size})
        return result.fetchall()

# ============================================================
# Adaptive rate limiter — reads Groq's actual response headers
# ============================================================

MAX_CHARS_PER_CHUNK = 7000
MIN_TOKENS_FOR_NEXT_CALL = 2000  # Don't send a request unless Groq says we have at least this many tokens left

def _parse_reset_time(reset_str):
    """Parses Groq's reset time string like '1m24.567s' or '34.12s' into seconds."""
    if not reset_str:
        return 60  # Default fallback
    
    seconds = 0.0
    reset_str = reset_str.strip()
    
    if "m" in reset_str:
        parts = reset_str.split("m")
        seconds += float(parts[0]) * 60
        reset_str = parts[1]
    
    if reset_str.endswith("s"):
        reset_str = reset_str[:-1]
    
    if reset_str:
        seconds += float(reset_str)
    
    return seconds

def wait_based_on_headers(response_headers):
    """
    Reads Groq's rate limit headers from the LAST successful response
    and proactively sleeps if we're running low on tokens or requests.
    """
    remaining_tokens = response_headers.get("x-ratelimit-remaining-tokens")
    remaining_requests = response_headers.get("x-ratelimit-remaining-requests")
    reset_tokens = response_headers.get("x-ratelimit-reset-tokens")
    reset_requests = response_headers.get("x-ratelimit-reset-requests")

    logger.info(
        f"Rate limit status — tokens left: {remaining_tokens}, "
        f"requests left: {remaining_requests}, "
        f"token reset: {reset_tokens}, request reset: {reset_requests}"
    )

    wait_time = 0.0

    # Check token budget
    if remaining_tokens is not None and int(remaining_tokens) < MIN_TOKENS_FOR_NEXT_CALL:
        token_wait = _parse_reset_time(reset_tokens)
        logger.info(f"Low token budget ({remaining_tokens} remaining). Waiting {token_wait:.1f}s for reset...")
        wait_time = max(wait_time, token_wait)

    # Check request budget
    if remaining_requests is not None and int(remaining_requests) <= 1:
        request_wait = _parse_reset_time(reset_requests)
        logger.info(f"Low request budget ({remaining_requests} remaining). Waiting {request_wait:.1f}s for reset...")
        wait_time = max(wait_time, request_wait)

    if wait_time > 0:
        time.sleep(wait_time + 1)  # +1s buffer

_last_response_headers = {}
def analyze_chunk(posts_chunk, max_retries=3):
    """
    Sends multiple posts in one LLM request. Returns a dict of post_id -> analysis.
    """
    global _last_response_headers
    
    if not API_KEY:
        logger.error("GROQ_API_KEY is not set.")
        return {}

    # If we have headers from a previous successful call, wait proactively
    if _last_response_headers:
        wait_based_on_headers(_last_response_headers)

    # 1. Build the multi-post prompt
    post_sections = []
    for post_id, title, body_text in posts_chunk:
        body = body_text or "(empty)"
        post_sections.append(f"--- POST post_id={post_id} ---\nTitle: {title}\nBody:\n{body}\n")
    
    user_content = "\n".join(post_sections)

    for attempt in range(max_retries):
        try:
            response = requests.post(
                LLM_API_URL,
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",   "content": user_content},
                    ],
                    "temperature": 0.1,
                },
                timeout=TIMEOUT, # Use the dynamic time out
            )
            
            # Catch 429 Too Many Requests specifically to wait longer
            if response.status_code == 429:
                retry_after = int(response.headers.get("retry-after", 30))
                logger.warning(f"Hit Groq Rate Limit (429). Retry-After: {retry_after}s. Waiting...")
                time.sleep(retry_after + 1)
                continue
                
            response.raise_for_status()
            _last_response_headers = dict(response.headers)  # Save headers for next call

            reply = response.json()["choices"][0]["message"]["content"].strip()
            parsed = _parse_llm_json_array(reply)

            if parsed is not None:
                results = {}
                for item in parsed:
                    pid = item.get("post_id")
                    if pid:
                        results[pid] = _sanitize_output(item)
                return results

            logger.warning(f"Attempt {attempt + 1}: Unparseable JSON array, retrying...")

        except requests.exceptions.Timeout:
            logger.warning(f"Attempt {attempt + 1}: Request timed out")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Attempt {attempt + 1}: Request error: {e}")

        if attempt < max_retries - 1:
            wait = 10 * (2 ** attempt)
            logger.info(f"Retrying in {wait}s...")
            time.sleep(wait)

    logger.error("Chunk failed after all retries.")
    return {}


def _parse_llm_json_array(raw_text):
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        text = text.rsplit("```", 1)[0].strip()

    try:
        result = json.loads(text)
        if isinstance(result, list): return result
        if isinstance(result, dict): return [result]
    except json.JSONDecodeError:
        pass

    start, end = text.find("["), text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            result = json.loads(text[start:end + 1])
            if isinstance(result, list): return result
        except json.JSONDecodeError:
            pass

    return None

def _sanitize_output(analysis):
    confidence = analysis.get("confidence_score")
    analysis["confidence_score"] = max(1, min(10, int(confidence))) if isinstance(confidence, (int, float)) else None
    pain = analysis.get("pain_intensity")
    analysis["pain_intensity"] = max(1, min(10, int(pain))) if isinstance(pain, (int, float)) else None
    
    valid_urgency = {"critical", "high", "medium", "low"}
    if analysis.get("urgency") not in valid_urgency: analysis["urgency"] = None
    
    valid_categories = {"SaaS", "Mobile App", "Desktop App", "Browser Extension", "API/Integration", "Marketplace", "CLI Tool", "Hardware+Software", "Other"}
    if analysis.get("product_category") not in valid_categories: analysis["product_category"] = "Other"
    
    valid_monetization = {"subscription", "freemium", "one-time purchase", "usage-based", "marketplace commission", "advertising", "open-source+paid-support"}
    if analysis.get("monetization_model") not in valid_monetization: analysis["monetization_model"] = None
    
    valid_market = {"large", "medium", "niche"}
    if analysis.get("market_size_signal") not in valid_market: analysis["market_size_signal"] = None
    
    tags = analysis.get("tags")
    analysis["tags"] = tags if isinstance(tags, list) else []
    analysis["is_valid_idea"] = bool(analysis.get("is_valid_idea", False))
    analysis["willingness_to_pay"] = bool(analysis.get("willingness_to_pay", False))
    return analysis

def save_idea(engine, post_id, analysis):
    query = insert_idea_query
    with engine.begin() as conn:
        conn.execute(query, {
            "post_id": post_id, "is_valid_idea": analysis["is_valid_idea"],
            "confidence_score": analysis.get("confidence_score"), "problem_statement": analysis.get("problem_statement"),
            "pain_intensity": analysis.get("pain_intensity"), "urgency": analysis.get("urgency"),
            "suggested_solution": analysis.get("suggested_solution"), "product_category": analysis.get("product_category"),
            "monetization_model": analysis.get("monetization_model"), "target_audience": analysis.get("target_audience"),
            "market_size_signal": analysis.get("market_size_signal"), "existing_alternatives": analysis.get("existing_alternatives"),
            "competitive_gap": analysis.get("competitive_gap"), "willingness_to_pay": analysis.get("willingness_to_pay", False),
            "tags": analysis.get("tags", []),
        })


# ============================================================
# Main orchestrator (Chunking Mode)
# ============================================================

def process_posts(engine, batch_size=50, max_workers=1):
    posts = get_unprocessed_posts(engine, batch_size=batch_size)
    if not posts:
        logger.info("No unprocessed posts.")
        return 0

    total = len(posts)
    logger.info(f"Processing {total} posts using dynamic chunks...")

    # Group posts dynamically based on characters
    chunks = []
    current_chunk = []
    current_chars = 0
    
    for post in posts:
        post_id, title, body_text = post
        body = body_text or "(empty)"
        # Calculate exactly how many characters this post will add to the prompt
        post_chars = len(f"--- POST post_id={post_id} ---\nTitle: {title}\nBody:\n{body}\n")
        
        # If adding this post goes over the limit, start a new chunk
        if current_chars + post_chars > MAX_CHARS_PER_CHUNK and current_chunk:
            chunks.append(current_chunk)
            current_chunk = []
            current_chars = 0
            
        current_chunk.append(post)
        current_chars += post_chars
        
    if current_chunk:
        chunks.append(current_chunk)
    
    processed = 0
    valid_count = 0
    failed = 0

    for i, chunk in enumerate(chunks, 1):
        logger.info(f"--- Chunk {i}/{len(chunks)} ({len(chunk)} posts) ---")
        
        results = analyze_chunk(chunk)

        if not results:
            logger.warning(f"Chunk {i} completely failed.")
            failed += len(chunk)
            continue

        for post_id, title, body_text in chunk:
            analysis = results.get(post_id)
            if not analysis:
                logger.warning(f"  [{post_id}] Missing from LLM response.")
                failed += 1
                continue

            try:
                save_idea(engine, post_id, analysis)
                processed += 1
                if analysis["is_valid_idea"]:
                    valid_count += 1
                    logger.info(f"{post_id} Valid Idea (score: {analysis.get('confidence_score')})")
                else:
                    logger.info(f"{post_id} Not an idea")
            except Exception as e:
                logger.error(f"  [{post_id}] DB save failed: {e}")
                failed += 1
        

    logger.info(f"Batch Complete: {processed}/{total} saved, {valid_count} valid ideas, {failed} failed.")
    return processed