import json
import os
import praw
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

CLIENTID = os.getenv("REDDIT_CLIENT_ID")
CLIENTSECRET = os.getenv("REDDIT_CLIENT_SECRET")
USERAGENT = os.getenv("REDDIT_USER_AGENT")

reddit = praw.Reddit(
    client_id=CLIENTID,
    client_secret=CLIENTSECRET,
    user_agent=USERAGENT
)

def explore_subreddits(subreddits, search_terms, limit_per_query=100):
    if isinstance(subreddits, (list, tuple)):
        joined_subreddits = "+".join(subreddits)
    else:
        joined_subreddits = str(subreddits)

    if isinstance(search_terms, str):
        search_terms = [search_terms]

    posts = {}
    subreddit_obj = reddit.subreddit(joined_subreddits)

    for term in search_terms:
        for submission in subreddit_obj.search(term, sort="new", syntax="lucene", limit=limit_per_query):
            if submission.id not in posts:
                posts[submission.id] = {
                    "Post_ID": submission.id,
                    "Title": submission.title,
                    "Subreddit": submission.subreddit.display_name,
                    "Score": submission.score,
                    "URL": submission.url,
                    "Created_UTC": submission.created_utc,
                    "Body_Text": submission.selftext[:500] + "..." if len(submission.selftext) > 500 else submission.selftext
                }

    df = pd.DataFrame(posts.values()).sort_values("Created_UTC", ascending=False)
    print(df.head())
    print(f"\nTotal unique posts found: {len(df)}")
    return df
