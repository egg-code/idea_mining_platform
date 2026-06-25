# 💡 Idea Mining Platform

> **Automated product opportunity discovery from Reddit using LLM-powered analysis.**

Mine Reddit posts at scale, enrich them with AI-driven product analysis, and surface validated startup ideas — all orchestrated through a containerized data pipeline.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Data Model](#data-model)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Environment Setup](#environment-setup)
  - [Quick Start](#quick-start)
- [Pipeline Guide](#pipeline-guide)
  - [Step 1 — Ingest Reddit Posts](#step-1--ingest-reddit-posts)
  - [Step 2 — dbt Staging Transformation](#step-2--dbt-staging-transformation)
  - [Step 3 — LLM Enrichment](#step-3--llm-enrichment)
  - [Step 4 — dbt Marts](#step-4--dbt-marts)
  - [Full Pipeline](#full-pipeline)
- [LLM Analysis Output Schema](#llm-analysis-output-schema)
- [Configuration](#configuration)
  - [Reddit Config](#reddit-config)
  - [LLM Prompt Engineering](#llm-prompt-engineering)
- [Useful Commands](#useful-commands)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

The **Idea Mining Platform** solves a simple problem: *How do you find validated product ideas at scale?*

People on Reddit constantly ask for tools that don't exist, complain about broken workflows, and describe unmet needs. This platform:

1. **Extracts** thousands of posts from targeted subreddits using the Reddit API (PRAW)
2. **Cleans** raw data through dbt staging transformations
3. **Enriches** each post with structured product-opportunity analysis via LLM (Groq / Ollama)
4. **Surfaces** the highest-signal ideas ranked by pain intensity, confidence, and community engagement

The result is a curated database of product ideas with problem statements, target audiences, monetization models, and competitive analysis — ready for product teams, indie hackers, and investors.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Compose                           │
│                                                                 │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │  Reddit   │───▶│  PostgreSQL  │◀───│    dbt (Staging +    │  │
│  │  Ingest   │    │     (DB)     │    │       Marts)         │  │
│  │  (PRAW)   │    │              │    └──────────────────────┘  │
│  └──────────┘    │  raw.*       │                               │
│                  │  staging.*   │    ┌──────────────────────┐  │
│  ┌──────────┐   │  marts.*     │◀───│    LLM Enrichment    │  │
│  │  Ollama   │   │              │    │  (Groq API / Ollama) │  │
│  │ (Optional)│   └──────────────┘    └──────────────────────┘  │
│  └──────────┘                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Reddit API ──▶ raw.subreddit_data ──▶ staging.cleaned_reddit ──▶ staging.llm_outputs ──▶ marts.analysis_ideas
   (PRAW)         (Python upsert)        (dbt staging)            (LLM processor)         (dbt marts)
```

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Language** | Python 3.11 | Pipeline orchestration & scripts |
| **Database** | PostgreSQL 16 | Persistent data storage |
| **Data Transformation** | dbt (1.9.0) | SQL-based staging & mart models |
| **Reddit API** | PRAW | Reddit post extraction |
| **LLM Inference** | Groq API / Ollama | Product opportunity analysis |
| **Containerization** | Docker Compose | Service orchestration |
| **ORM** | SQLAlchemy 2.0 | Database connectivity |
| **Build Tool** | Make | Pipeline command shortcuts |

---

## Project Structure

```
idea_mining_platform/
│
├── main.py                          # Pipeline entry point (ingest / llm modes)
├── Dockerfile                       # Python app container
├── docker-compose.yml               # Multi-service orchestration
├── Makefile                         # Pipeline shortcuts (make ingest, make llm, etc.)
├── requirements.txt                 # Python dependencies
├── .env                             # API keys (gitignored)
├── .gitignore
│
├── scripts/
│   ├── reddit_e.py                  # Reddit extraction via PRAW
│   └── llm_processor.py            # LLM enrichment engine (chunking + retry)
│
├── config/
│   ├── reddit_config.json           # Subreddits & search terms
│   ├── prompts.py                   # System prompt for LLM analysis
│   └── queries.py                   # SQL queries (upsert, fetch unprocessed)
│
├── init-db/
│   └── init_schema.sql              # PostgreSQL schema (raw, staging, marts)
│
└── dbt/
    ├── dbt_project.yml              # dbt project configuration
    ├── profiles.yml                 # dbt database connection
    └── app_ideas/
        ├── models/
        │   ├── source.yml           # Source definitions & tests
        │   ├── staging/
        │   │   └── cleaned_reddit.sql   # Staging: clean raw posts
        │   └── marts/
        │       └── analysis_ideas.sql   # Mart: enriched idea analysis
        └── macros/
            └── generate_schema_name.sql # Custom schema routing
```

---

## Data Model

### Database Schemas

The platform uses a **layered data warehouse** pattern with three schemas:

#### `raw` — Raw ingested data
| Table | Description |
|-------|-------------|
| `subreddit_data` | Raw Reddit posts (post_id PK, title, subreddit, score, url, body_text, created_utc) |

#### `staging` — Cleaned & enriched data
| Table | Description |
|-------|-------------|
| `cleaned_reddit` | dbt-transformed posts with proper timestamps (materialized table) |
| `llm_outputs` | LLM analysis results per post (FK → subreddit_data, ON DELETE CASCADE) |

#### `marts` — Business-ready analytics
| Table | Description |
|-------|-------------|
| `analysis_ideas` | Joined view of validated ideas ranked by pain × confidence × score |

### Entity Relationship

```
raw.subreddit_data (1) ──── (0..1) staging.llm_outputs
        │                              │
        └──── staging.cleaned_reddit ──┘
                      │
              marts.analysis_ideas
              (only is_valid_idea = true)
```

---

## Getting Started

### Prerequisites

- **Docker** & **Docker Compose** (v2+)
- **Reddit API credentials** — [Create an app at reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)
- **Groq API key** (free tier) — [Get one at console.groq.com](https://console.groq.com) — *OR* use local Ollama

### Environment Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/<your-username>/idea_mining_platform.git
   cd idea_mining_platform
   ```

2. **Create your `.env` file:**
   ```bash
   cp .env.example .env
   ```

   Fill in your credentials:
   ```env
   # Reddit API
   CLIENT_ID=your_reddit_client_id
   CLIENT_SECRET=your_reddit_client_secret
   USER_AGENT=AppIntelExplorer/1.0 by your-username

   # LLM Provider
   GROQ_API_KEY=your_groq_api_key
   ```

3. **Build the containers:**
   ```bash
   make build
   ```

### Quick Start

Run the entire pipeline end-to-end with a single command:

```bash
make pipeline
```

This will:
1. Start PostgreSQL + Ollama services
2. Ingest Reddit posts → `raw.subreddit_data`
3. Run dbt staging → `staging.cleaned_reddit`
4. Run LLM enrichment → `staging.llm_outputs`
5. Build dbt marts → `marts.analysis_ideas`

Check results:
```bash
make status
```

---

## Pipeline Guide

### Step 1 — Ingest Reddit Posts

```bash
make ingest
```

- Connects to the Reddit API via PRAW
- Searches across **18 subreddits** using **30+ search queries** (see `config/reddit_config.json`)
- Deduplicates posts by `post_id`
- Upserts into `raw.subreddit_data` (skips existing posts via `ON CONFLICT DO NOTHING`)

### Step 2 — dbt Staging Transformation

```bash
make dbt-staging
```

- Converts `created_utc` (Unix epoch float) → proper `TIMESTAMP`
- Materializes as a table in `staging.cleaned_reddit`

### Step 3 — LLM Enrichment

```bash
make llm
```

- Fetches unprocessed posts (no matching row in `staging.llm_outputs`)
- Processes in **chunks of 5 posts per API call** (free-tier safe)
- Each post is analyzed by the LLM with a structured product-strategist prompt
- Implements retry logic with exponential backoff + 429 rate-limit handling
- Results are sanitized (enum validation, score clamping) before database insert
- **Rate limiting**: 2.5s sleep between chunks to stay under Groq's 30 req/min free tier

### Step 4 — dbt Marts

```bash
make dbt-marts
```

- Joins `cleaned_reddit` + `llm_outputs`
- Filters to `is_valid_idea = true` only
- Orders by `pain_intensity DESC`, `confidence_score DESC`, `score DESC`
- Materializes in `marts.analysis_ideas`

### Full Pipeline

```bash
make pipeline    # Runs all 4 steps sequentially
make status      # Shows row counts across all tables
```

---

## LLM Analysis Output Schema

Each Reddit post is analyzed and scored across these dimensions:

| Field | Type | Description |
|-------|------|-------------|
| `is_valid_idea` | `boolean` | Whether the post describes an actionable, unmet product need |
| `confidence_score` | `1-10` | Confidence in the classification |
| `problem_statement` | `text` | Extracted problem description |
| `pain_intensity` | `1-10` | Severity of the user's problem |
| `urgency` | `enum` | `critical` \| `high` \| `medium` \| `low` |
| `suggested_solution` | `text` | LLM-proposed product solution |
| `product_category` | `enum` | `SaaS` \| `Mobile App` \| `Desktop App` \| `Browser Extension` \| `API/Integration` \| `Marketplace` \| `CLI Tool` \| `Hardware+Software` \| `Other` |
| `monetization_model` | `enum` | `subscription` \| `freemium` \| `one-time purchase` \| `usage-based` \| `marketplace commission` \| `advertising` \| `open-source+paid-support` |
| `target_audience` | `text` | Who would use this product |
| `market_size_signal` | `enum` | `large` \| `medium` \| `niche` |
| `existing_alternatives` | `text` | Current tools / workarounds mentioned |
| `competitive_gap` | `text` | What's missing from alternatives |
| `willingness_to_pay` | `boolean` | Signals of budget or payment intent |
| `tags` | `text[]` | 3-5 keyword tags for categorization |

---

## Configuration

### Reddit Config

Edit `config/reddit_config.json` to customize:

- **`subreddits`** — Which subreddits to scrape (currently 18 communities covering apps, devops, productivity, startups)
- **`search_terms`** — Natural language queries like *"is there an app that"*, *"need a tool to"*, *"I wish there was"* (currently 30+ patterns)
- **`limit_per_query`** — Max posts per search term per subreddit (default: 100)

### LLM Prompt Engineering

The system prompt in `config/prompts.py` is carefully engineered with:

1. **Role framing** — "Senior product strategist at a venture studio"
2. **Scoring rubrics** — Numeric scales with anchor examples for consistency
3. **Market signal extraction** — Looks for buying signals, frustration words, budget mentions
4. **Explicit null handling** — Prevents hallucinated fields for non-ideas
5. **Multi-post chunking** — Processes 5 posts per API call for efficiency

---

## Useful Commands

| Command | Description |
|---------|-------------|
| `make up` | Start infrastructure (PostgreSQL + Ollama) |
| `make down` | Stop all containers |
| `make down-reset` | Stop all + **delete database volumes** |
| `make build` | Rebuild Docker images after code changes |
| `make ingest` | Run Reddit extraction |
| `make dbt-staging` | Run dbt staging models |
| `make llm` | Run LLM enrichment |
| `make dbt-marts` | Build analytics marts |
| `make pipeline` | Run full pipeline (ingest → staging → llm → marts) |
| `make status` | Show row counts across all pipeline tables |
| `make test` | Run dbt tests |

---

## Querying Your Ideas

Once the pipeline completes, connect to PostgreSQL and explore your ideas:

```bash
# Connect to the database
docker exec -it idea_mining_db psql -U admin -d app_ideas
```

```sql
-- Top 10 highest-pain validated ideas
SELECT title, problem_statement, pain_intensity, confidence_score,
       product_category, monetization_model, target_audience
FROM marts.analysis_ideas
ORDER BY pain_intensity DESC, confidence_score DESC
LIMIT 10;

-- Ideas by product category
SELECT product_category, COUNT(*) as idea_count,
       ROUND(AVG(pain_intensity), 1) as avg_pain,
       ROUND(AVG(confidence_score), 1) as avg_confidence
FROM marts.analysis_ideas
GROUP BY product_category
ORDER BY idea_count DESC;

-- Ideas where users are willing to pay
SELECT title, problem_statement, suggested_solution, monetization_model
FROM marts.analysis_ideas
WHERE willingness_to_pay = true
ORDER BY pain_intensity DESC;

-- Pipeline status overview
SELECT 'raw.subreddit_data' as layer, count(*) FROM raw.subreddit_data
UNION ALL
SELECT 'staging.cleaned_reddit', count(*) FROM staging.cleaned_reddit
UNION ALL
SELECT 'staging.llm_outputs', count(*) FROM staging.llm_outputs
UNION ALL
SELECT 'marts.analysis_ideas', count(*) FROM marts.analysis_ideas;
```

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

---

## License

This project is for educational and personal use. See [LICENSE](LICENSE) for details.

---

<p align="center">
  Built with ❤️ by <a href="https://github.com/your-username">eggcoder</a>
</p>
