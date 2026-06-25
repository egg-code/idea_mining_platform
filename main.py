import os
import json
import argparse
import logging
from sqlalchemy import create_engine, text
import pandas as pd
from scripts.reddit_e import explore_subreddits
from scripts.llm_processor import process_posts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

def create_db_connection():
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    DB_NAME = os.getenv("DB_NAME")

    if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
        logger.error("Database credentials are not fully set in the environment variables.")
        raise ValueError("Missing required DB credentials.")

    connection_string = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(connection_string, pool_pre_ping=True)

def upsert_posts(engine, df):
    """Insert posts into raw.subreddit_data, skipping duplicates on primary key conflict."""
    query = text("""
        INSERT INTO raw.subreddit_data (post_id, title, subreddit, score, url, created_utc, body_text)
        VALUES (:post_id, :title, :subreddit, :score, :url, :created_utc, :body_text)
        ON CONFLICT (post_id) DO NOTHING
    """)
    inserted = 0
    with engine.begin() as conn:
        for _, row in df.iterrows():
            res = conn.execute(query, {
                "post_id": row["post_id"],
                "title": row["title"],
                "subreddit": row["subreddit"],
                "score": row["score"],
                "url": row["url"],
                "created_utc": row["created_utc"],
                "body_text": row["body_text"]
            })
            inserted += res.rowcount
    return inserted

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reddit Extraction & LLM Enrichment Pipeline")
    parser.add_argument("--mode", choices=["ingest", "llm", "batch"], required=True, help="Pipeline execution mode")
    args = parser.parse_args()

    engine = create_db_connection()

    if args.mode == "ingest":
        logger.info("Starting Reddit Ingestion Mode...")
        config_path = "config/reddit_config.json"
        with open(config_path, "r") as f:
            config = json.load(f)

        df = explore_subreddits(
            config["subreddits"],
            config["search_terms"],
            limit_per_query=config.get("limit_per_query", 100)
        )

        if df is not None and not df.empty:
            inserted = upsert_posts(engine, df)
            logger.info(f"Ingestion complete: Ingested {len(df)} posts ({inserted} new, {len(df) - inserted} duplicates skipped)")
        else:
            logger.warning("No data retrieved during ingestion.")

    elif args.mode == "llm":
        logger.info("Starting LLM Enrichment Mode...")
        MODEL_NAME = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
        MAX_WORKERS = int(os.getenv("LLM_WORKERS", 1))
        
        total_processed = 0
        batch_num = 0

        while True:
            batch_num += 1
            logger.info(f"--- Batch {batch_num} (workers={MAX_WORKERS}) ---")

            processed = process_posts(engine, batch_size=50, max_workers=MAX_WORKERS)
            total_processed += processed

            if processed == 0:
                logger.info("No more unprocessed posts found. LLM enrichment complete.")
                break
        
        logger.info(f"LLM enrichment complete: {total_processed} posts processed across {batch_num} batches.")
