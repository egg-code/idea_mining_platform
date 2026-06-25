CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS marts;

-- Table to store raw subreddit data
CREATE TABLE IF NOT EXISTS raw.subreddit_data (
    post_id VARCHAR(50) PRIMARY KEY,
    title TEXT NOT NULL,
    subreddit VARCHAR(100) NOT NULL,
    score INTEGER DEFAULT 0,
    url TEXT,
    created_utc DOUBLE PRECISION,  -- Raw unix epoch float
    body_text TEXT,
    extracted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);


-- Table to store LLM output
-- ============================================================
-- raw.extracted_ideas — stores LLM analysis results
-- ============================================================
-- KEY CONCEPT: REFERENCES creates a Foreign Key.
-- This guarantees every row in extracted_ideas points to a
-- real post in subreddit_data. ON DELETE CASCADE means if
-- you delete a post, its analysis is auto-deleted too.
-- ============================================================
CREATE TABLE IF NOT EXISTS staging.llm_outputs (
    post_id               VARCHAR(50) PRIMARY KEY 
                          REFERENCES raw.subreddit_data(post_id) ON DELETE CASCADE,
    is_valid_idea         BOOLEAN NOT NULL,
    confidence_score      SMALLINT,
    problem_statement     TEXT,
    pain_intensity        SMALLINT,
    urgency               VARCHAR(20),
    suggested_solution    TEXT,
    product_category      VARCHAR(50),
    monetization_model    VARCHAR(50),
    target_audience       TEXT,
    market_size_signal    VARCHAR(20),
    existing_alternatives TEXT,
    competitive_gap       TEXT,
    willingness_to_pay    BOOLEAN,
    tags                  TEXT[],
    extracted_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);