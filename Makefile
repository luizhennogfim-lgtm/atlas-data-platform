.PHONY: install lint test test-unit up down rebuild logs run-local sample

install:        ## local dev environment (Python 3.12)
	pip install -r requirements-dev.txt

lint:
	ruff check .

test-unit:      ## no database needed; integration tests are skipped
	pytest -q

test:           ## needs PostgreSQL: createdb atlas_test, then export ATLAS_TEST_DSN
	pytest -q

up:
	docker compose up -d --build

down:           ## stops containers, KEEPS the data volume
	docker compose down

rebuild:
	docker compose build --no-cache && docker compose up -d

logs:
	docker compose logs -f --tail=100

sample:
	python -m pipeline.cli generate-data

run-local:      ## runs the whole pipeline once without Airflow
	python -m pipeline.cli run
