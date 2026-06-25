from datetime import datetime
import json
import os
import praw
import pandas as pd
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)


def explore_subreddits(subreddits, search_terms, limit_per_query=100):

    reddit = praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent=os.getenv("REDDIT_USER_AGENT")
    )
    
    if isinstance(subreddits, (list, tuple)):
        joined_subreddits = "+".join(subreddits)
    else:
        joined_subreddits = str(subreddits)

    if isinstance(search_terms, str):
        search_terms = [search_terms]

    posts = {}
    subreddit_obj = reddit.subreddit(joined_subreddits)

    for term in search_terms:
        for submission in subreddit_obj.search(term, sort="new", syntax="lucene", 
                                               time_filter="all", limit=limit_per_query):
            if submission.id not in posts:
                posts[submission.id] = {
                    "post_id": submission.id,
                    "title": submission.title,
                    "subreddit": submission.subreddit.display_name,
                    "score": submission.score,
                    "url": submission.url,
                    "created_utc": submission.created_utc,
                    "body_text": submission.selftext,
                    "extracted_at": datetime.now().isoformat()
                }

    df = pd.DataFrame(posts.values()).sort_values("created_utc", ascending=False)
    logger.info(f"Extracted {len(df)} posts from subreddits")
    return df
