import json
from sqlalchemy import create_engine, text
import os
import pandas as pd
from scripts.reddit_e import explore_subreddits
from scripts.ollama_utils import ensure_model
from dotenv import load_dotenv
import logging
from datetime import datetime

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

try:
    MODEL_NAME = os.getenv("LLM_MODEL", "llama3.2:3b")
    ensure_model(model_name=MODEL_NAME)

except Exception as e:
    logger.error(f"Failed to ensure Ollama model: {e}", exc_info=True)
    raise

def create_db_connection():
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    DB_NAME = os.getenv("DB_NAME")

    if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
        logger.error("Database credentials are not fully set in the environment variables.")
        raise ValueError("Missing required DB credentials.")
    

    connection_string = (
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    engine = create_engine(
        connection_string,
        pool_size=10,  #Number of connections to keep in the pool
        max_overflow=20,  #Number of connections to allow beyond the pool_size
        pool_pre_ping=True) #Ensures connections are valid before using them
    logger.info("Database connection established.")
    
    return engine


def validate_df(df: pd.DataFrame) -> None:
    """Basic DataFrame validation before insert."""
    if df.empty:
        raise ValueError("DataFrame is empty; no data to insert.")
    null_rows = df.isnull().all(axis=1).sum()
    if null_rows > 0:
        logger.warning(f"Found {null_rows} rows that are entirely NULL")



if __name__ == "__main__":
    start_time = datetime.now()
    logger.info("Reddit data load job started")

    try:
        # Load config
        config_path = "config/reddit_config.json"
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "r") as f:
            config = json.load(f)

        subreddits = config.get("subreddits", [])
        search_terms = config.get("search_terms", [])
        limit_per_query = config.get("limit_per_query", 100)

        if not subreddits or not search_terms:
            raise ValueError("subreddits and search_terms must be non-empty in config")

        logger.info(f"Exploring {len(subreddits)} subreddits with {len(search_terms)} search terms")

        # Extract Reddit data
        df = explore_subreddits(subreddits, search_terms, limit_per_query=limit_per_query)

        if df is None or df.empty:
            logger.error("No data returned from explore_subreddits")
            raise ValueError("No Reddit data extracted")

        validate_df(df)
        logger.info(f"Extracted {len(df)} rows with columns: {df.columns.tolist()}")

        # DB connection
        engine = create_db_connection()

        # Table name: use schema="raw" and a deterministic name
        table_name = "subreddit_data"

        # Batch insert for PostgreSQL: chunksize + method='multi' [web:20][web:23][web:26][web:29]
        chunksize = 5000  # 5K rows per batch is a good default [web:26]

        df.to_sql(
            table_name,
            engine,
            if_exists="append",
            index=False,
            schema="raw",
            chunksize=chunksize,
            method="multi",  # Better performance with PostgreSQL [web:29]
        )

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"Data inserted into raw.{table_name} successfully ({elapsed:.2f}s, {len(df)} rows)")

    except Exception as e:
        logger.error(f"Job failed: {e}", exc_info=True)
        raise