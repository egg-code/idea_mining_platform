.PHONY: up down ingest dbt-staging llm dbt-marts pipeline status

help:
	@echo "Makefile Commands:"
	@echo "  up            - Start the infrastructure (Postgres, Ollama)"
	@echo "  down          - Stop the infrastructure"
	@echo "  down-reset    - Stop and remove volumes to reset database"
	@echo "  build         - Build Docker images for code changes"
	@echo "  ingest        - Ingest Reddit posts into raw layer"
	@echo "  dbt-staging   - Run dbt staging models to clean data"
	@echo "  llm           - Run LLM enrichment on cleaned data"
	@echo "  dbt-marts     - Build marts with enriched data"
	@echo "  audit         - Review LLM outputs for quality"
	@echo "  pipeline      - Run the full pipeline end-to-end"
	@echo "  status        - Check row counts in key tables"
	@echo "  test          - Run dbt tests"

# ---- Infrastructure ----

up:
	docker compose up -d
	@echo "Waiting for services to be healthy..."
	@sleep 5

up-build:
	docker compose up -d --build
	@echo "Waiting for services to be healthy..."
	@sleep 5

down:
	docker compose down

# ---- Remove volumes to reset database ----
down-reset:
	docker compose down -v 

# ---- Build for code changes ----
build:
	docker compose build 

# ---- Pipeline Steps ----
ingest:
	@echo "Step 1: Ingesting Reddit posts..."
	docker compose run --rm ingest

dbt-staging:
	@echo "Step 2: Running dbt staging models..."
	docker compose run --rm dbt run --select staging

llm:
	@echo "Step 3: Running LLM enrichment..."
	docker compose run --rm llm

dbt-marts:
	@echo "Step 4: Building marts..."
	docker compose run --rm dbt dbt run --select marts

audit:
	@echo "Audit: Reviewing LLM outputs for quality..."
	docker cp scripts/audit_data_quality.sql idea_mining_db:/tmp/audit_data_quality.sql
	docker exec idea_mining_db psql -U admin -d app_ideas -f /tmp/audit_data_quality.sql

# ---- Full Pipeline ----
pipeline: up ingest dbt-staging llm dbt-marts
	@echo ""
	@echo "Pipeline complete!"
	@echo "   Run 'make status' to see results."

# ---- Utilities ----
status:
	@echo "Pipeline Status:"
	@docker exec idea_mining_db psql -U admin -d app_ideas -c \
		"SELECT 'raw.subreddit_data' as table_name, count(*) FROM raw.subreddit_data \
		 UNION ALL \
		 SELECT 'staging.cleaned_reddit', count(*) FROM staging.cleaned_reddit \
		 UNION ALL \
		 SELECT 'staging.llm_outputs', count(*) FROM staging.llm_outputs \
		 UNION ALL \
		 SELECT 'marts.analysis_ideas', count(*) FROM marts.analysis_ideas;"

test:
	docker compose run --rm dbt test