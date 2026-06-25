# 💡 Idea Mining Platform

> **Automated product opportunity discovery from Reddit using LLM-powered analysis.**

Mine Reddit posts at scale, enrich them with AI-driven product analysis, and surface validated startup ideas — all orchestrated through a containerized data pipeline.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Key Optimizations & Resilience](#key-optimizations--resilience)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Data Model](#data-model)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Environment Setup](#environment-setup)
  - [Quick Start](#quick-start)
- [Pipeline Guide](#pipeline-guide)
- [Data Quality Audit](#data-quality-audit)
- [Configuration](#configuration)
- [LLM Analysis Output Schema](#llm-analysis-output-schema)
- [Useful Commands](#useful-commands)
- [License](#license)

---

## Overview

The **Idea Mining Platform** solves a simple problem: *How do you find validated product ideas at scale?*

People on Reddit constantly ask for tools that don't exist, complain about broken workflows, and describe unmet needs. This platform:

1. **Extracts** thousands of posts from targeted subreddits using the Reddit API (PRAW)
2. **Cleans** raw data through dbt staging transformations
3. **Enriches** each post with structured product-opportunity analysis via LLM (Groq API / Ollama)
4. **Surfaces** the highest-signal ideas ranked by pain intensity, confidence, and community engagement

The result is a curated database of product ideas with problem statements, target audiences, monetization models, and competitive analysis — ready for product teams, indie hackers, and investors.

---

## Architecture

```text
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

```text
Reddit API ──▶ raw.subreddit_data ──▶ staging.cleaned_reddit ──▶ staging.llm_outputs ──▶ marts.analysis_ideas
   (PRAW)         (Python upsert)        (dbt staging)            (LLM processor)         (dbt marts)
```

---

## Key Optimizations & Resilience

This pipeline is engineered for production-grade reliability, featuring several advanced optimizations:

1. **Idempotent Ingestion (`ON CONFLICT DO NOTHING`)**: The Reddit extractor uses a custom SQLAlchemy upsert method. You can run ingestion as many times as you want without crashing the database or duplicating primary keys (`post_id`).
2. **Decoupled Orchestration (`main.py`)**: Python services are split into `--mode ingest` and `--mode llm`. This allows dbt transformations to run *between* extraction and LLM processing.
3. **Adaptive LLM Rate Limiting**: Instead of naive fixed sleep times, the LLM processor actively parses Groq API headers (`x-ratelimit-remaining-tokens`, `reset-requests`). It dynamically pauses execution *only* when the token budget is near exhaustion.
4. **Dynamic Context Chunking**: Posts are dynamically batched into the LLM context window based on exact character counts (7,000 char chunks) rather than a fixed number of posts. This maximizes token usage without triggering payload limits.
5. **Custom DBT Schema Routing**: Uses a custom `generate_schema_name.sql` macro to bypass default dbt behavior, ensuring tables compile directly into `staging` and `marts` without user-prefixed schemas (e.g., preventing `dev_marts`).
6. **Data Quality Auditing**: Includes a comprehensive SQL audit script (`make audit`) to monitor LLM hallucination rates, null distributions, and classification accuracy.

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

```text
idea_mining_platform/
│
├── main.py                          # Pipeline entry point (ingest / llm modes)
├── Dockerfile                       # Python app container
├── docker-compose.yml               # Multi-service orchestration
├── Makefile                         # Pipeline shortcuts (make ingest, make llm, etc.)
├── requirements.txt                 # Python dependencies
├── .env                             # Real API keys (gitignored)
├── .env.example                     # Template config for safe sharing
├── .gitignore
│
├── scripts/
│   ├── reddit_e.py                  # Reddit extraction via PRAW
│   ├── llm_processor.py             # LLM enrichment engine (chunking + retry)
│   └── audit_data_quality.sql       # Pipeline QA queries
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
        │   │   ├── cleaned_reddit.sql   # Staging: clean raw posts
        │   │   └── schema.yml
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
| `cleaned_reddit` | dbt-transformed posts with proper timestamps (`to_timestamp` cast) |
| `llm_outputs` | LLM analysis results per post (FK → subreddit_data, ON DELETE CASCADE) |

#### `marts` — Business-ready analytics
| Table | Description |
|-------|-------------|
| `analysis_ideas` | Joined view of validated ideas ranked by pain × confidence × score |

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

3. **Fill in your credentials in `.env`:**
   Your `.env` must contain the following variables:
   * `LLM_PROVIDER` (`cloud` or `local`)
   * `GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_API_URL`
   * `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`
   * `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`

4. **Build the containers:**
   ```bash
   make build
   ```

### Quick Start

Run the entire pipeline end-to-end with a single command:

```bash
make pipeline
```

Check pipeline progression:
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
- Upserts safely into `raw.subreddit_data` without duplicating `post_id`.

### Step 2 — dbt Staging Transformation

```bash
make dbt-staging
```

- Converts `created_utc` (Unix epoch float) → proper `TIMESTAMP WITH TIME ZONE`
- Materializes as a table in `staging.cleaned_reddit`

### Step 3 — LLM Enrichment

```bash
make llm
```

- Fetches unprocessed posts (no matching row in `staging.llm_outputs`)
- Groups posts dynamically into 7,000 character chunks.
- The LLM parses the chunk and extracts structured JSON product analysis.
- **Adaptive Rate Limiting**: The script monitors Groq's token reset headers, only pausing execution when token budgets drop below 2000.

### Step 4 — dbt Marts

```bash
make dbt-marts
```

- Joins `staging.cleaned_reddit` + `staging.llm_outputs`
- Filters out non-ideas (`is_valid_idea = true`)
- Orders by `pain_intensity DESC`, `confidence_score DESC`
- Materializes in `marts.analysis_ideas`

---

## Data Quality Audit

To monitor the performance of the LLM and the health of your dataset, we included a comprehensive SQL audit script.

```bash
make audit
```

This will output a terminal report covering:
1. **Valid vs Invalid Idea Split** (Hit rate of the LLM classification)
2. **Confidence Score & Pain Intensity Distribution**
3. **Missing Value Check** (Detects LLM hallucinations/omissions for key fields)
4. **Spot Checks** (Displays the top 10 highest confidence ideas and borderline cases directly in the console)

---

## Configuration

### Reddit Config
Edit `config/reddit_config.json` to customize subreddits, search terms, and the `limit_per_query` cap.

### LLM Prompt Engineering
The system prompt in `config/prompts.py` is carefully engineered with:
1. **Role framing** — "Senior product strategist at a venture studio"
2. **Scoring rubrics** — Numeric scales with anchor examples for consistency
3. **Market signal extraction** — Looks for buying signals, frustration words, budget mentions
4. **Explicit null handling** — Prevents hallucinated fields for non-ideas

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

## Useful Commands

| Command | Description |
|---------|-------------|
| `make up` | Start infrastructure (PostgreSQL + Ollama) |
| `make up-build` | Rebuild and start infrastructure |
| `make down` | Stop all containers |
| `make down-reset` | Stop all + **delete database volumes** (resets everything) |
| `make ingest` | Run Reddit extraction (`main.py --mode ingest`) |
| `make llm` | Run LLM enrichment (`main.py --mode llm`) |
| `make dbt-staging` | Run dbt staging models (`dbt run --select staging`) |
| `make dbt-marts` | Build analytics marts (`dbt run --select marts`) |
| `make pipeline` | Run full pipeline (ingest → staging → llm → marts) |
| `make status` | Show row counts across all pipeline tables |
| `make audit` | Run the Data Quality Audit script to verify LLM outputs |
| `make test` | Run dbt tests |

---

## License

This project is for educational and personal use. See [LICENSE](LICENSE) for details.

---

<p align="center">
  Built with ❤️ by <a href="https://github.com/your-username">eggcoder</a>
</p>
