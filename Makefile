.PHONY: up db test evals sync nudge web

up:        ## Postgres + API on :8000, docs at /docs
	docker compose up -d --build

db:        ## Recreate schema and views from scratch (destructive)
	docker compose exec -T db psql -U funnel -d funnel -f /docker-entrypoint-initdb.d/schema.sql
	docker compose exec -T db psql -U funnel -d funnel -f /docker-entrypoint-initdb.d/views.sql

test:      ## Unit tests. No tokens spent.
	cd api && pytest -q

evals:     ## Score the golden set and compare against the recorded baseline. Spends tokens.
	cd api && python -m app.evals.harness app/evals/goldens.jsonl

sync:      ## Render the Obsidian vault from the database
	cd api && python -m app.cli sync

nudge:     ## Applications past the 7-day silence window
	cd api && python -m app.cli nudge

web:
	cd web && npm run dev
