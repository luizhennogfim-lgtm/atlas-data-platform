# Atlas Data Platform

A small, reproducible data platform for a **fictional e-commerce company**: CSV files go in, validated analytical
tables come out. It shows the pieces a data team actually relies on: layered storage, SQL transformations with
tests, orchestration, data-quality gates, an auditable run history and CI.

> All data is synthetic. Any figure produced by this project is a **demonstration**, not a business result.

## Business problem

The business wants trustworthy answers to: revenue by day and month, best-selling products, average order value,
repeat-purchase rate, fastest-growing categories and products, how many records are invalid, and how fresh the data
is. Raw files contain duplicates, impossible dates, negative prices and orphan keys, so the platform has to
**detect, explain and quarantine** bad records instead of silently counting them or crashing.

## Architecture

```mermaid
flowchart LR
    CSV[CSV files] --> ING[Python ingestion]
    ING --> BRZ[(Bronze: raw text + lineage)]
    BRZ --> SLV[(Silver: typed, validated, de-duplicated)]
    SLV --> REJ[(rejected_records)]
    SLV --> GLD[(gold_candidate)]
    GLD -->|tests + quality gate pass| PUB{{atomic swap}}
    PUB --> LIVE[(gold)]
    ING -.-> OPS[(ops: runs, steps, checks)]
    SLV -.-> OPS
    OPS --> RPT[quality_report.md]
```

Details and design rationale: [docs/architecture.md](docs/architecture.md).

## Technology stack

| Tool | Used for |
|---|---|
| Python 3.12 + psycopg 3 | Ingestion, run tracking, quality checks, CLI |
| PostgreSQL 16 | Bronze / Silver / Gold / Ops storage |
| dbt Core 1.11 (`dbt-postgres` 1.11) | Silver and Gold transformations and data tests |
| Apache Airflow 2.10 | Orchestration (one DAG) |
| Docker Compose | Local PostgreSQL + Airflow |
| pytest, ruff | Tests and linting |
| GitHub Actions | CI |
| AWS S3 (optional) | Export of the quality report. Off by default; nothing needs an AWS account |

Versions are pinned in `pyproject.toml`, `requirements*.txt` and the `Dockerfile`.

## Data flow

1. **Bronze** - each file is hashed (SHA-256). Unseen content is loaded in one transaction as raw text with
   `_file_id`, `_row_number`, `_ingested_at`. Bronze is never overwritten.
2. **Silver** (dbt) - cast, normalise, de-duplicate (latest ingestion wins) and validate. Every excluded row goes
   to `silver.rejected_records` with a reason.
3. **Gold** (dbt) - facts, dimensions and metric tables, built in `gold_candidate`.
4. **Publish** - after dbt tests and quality gates pass, `gold_candidate` is renamed to `gold` in one transaction.

**Idempotency:** the same file content is loaded once, and Silver/Gold are rebuilt from Bronze, so re-running a
load cannot duplicate results (covered by `tests/test_loader.py` and `tests/test_pipeline.py`).

## Data quality strategy

- Critical failures (missing/invalid source file, no valid rows, rejection rate above 20%, any failing dbt test)
  stop the run **before publication**; the previous Gold stays online.
- Warnings (rejection rate above 1%, duplicates found) are recorded and shown, but do not stop the run.
- Every run records record counts per source, rejected and duplicate counts, per-step durations, failure messages
  and the last successful run in `ops.*`, and writes `reports/quality_report.md`.

See [docs/data_quality.md](docs/data_quality.md) and [docs/metrics.md](docs/metrics.md) (metric definitions and
validation rules).

## Installation and setup

### Option A - Docker Compose (PostgreSQL + Airflow)

```bash
cp .env.example .env          # development credentials only
docker compose up -d --build
# Airflow UI: http://localhost:8080  (user/password from .env)
# Unpause and trigger the DAG "atlas_pipeline"
docker compose ps             # status / health
docker compose logs -f airflow-scheduler
docker compose down           # stop, KEEPS data (volume pgdata)
docker compose build --no-cache && docker compose up -d   # rebuild
```

`docker compose down -v` also deletes the database volume. Use it only if you want a clean slate.

### Option B - Local Python (no Airflow, no Docker)

Requires Python 3.12 and a PostgreSQL 14+ you can connect to.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
createdb atlas && createdb atlas_test           # or use any database you own
export ATLAS_DB_DSN=postgresql://USER:PASSWORD@localhost:5432/atlas
python -m pipeline.cli run                      # full pipeline once
python -m pipeline.cli report                   # rewrite reports/quality_report.md
```

Other commands: `python -m pipeline.cli init-db`, `python -m pipeline.cli generate-data --seed 7`.

## Running the tests

```bash
pytest -q                                       # unit tests; integration tests skip without a database
export ATLAS_TEST_DSN=postgresql://USER:PASSWORD@localhost:5432/atlas_test
pytest -q                                       # + integration and end-to-end tests (needs dbt on PATH)
ruff check .
```

The test database name must end in `_test`; the fixture resets its schemas. Integration tests invoke dbt, so
the full suite takes a couple of minutes. Tests use a tiny deterministic dataset, no AWS and no external APIs.
DAG tests (`tests/test_dag.py`) run only where Apache Airflow is installed (CI has a dedicated job).

| Needs nothing | Needs PostgreSQL (+ dbt) | Needs Airflow | Needs Docker |
|---|---|---|---|
| lint, generator, quality-rule unit tests, S3 stub test | loader, end-to-end pipeline, analytics SQL | DAG structure tests | compose config/build |

## Example analytical queries

All in [`sql/analytics/`](sql/analytics), for example:

```sql
-- Top 10 products by units sold (completed orders only)
SELECT units_rank, product_id, product_name, units_sold, revenue
FROM gold.product_performance ORDER BY units_rank LIMIT 10;

-- Repeat purchase rate
SELECT * FROM gold.retention_summary;

-- Why were orders rejected?
SELECT reason, count(*) FROM silver.rejected_records
WHERE entity = 'orders' AND reason <> 'duplicate_key' GROUP BY reason;
```

## Repository layout

```text
dags/                 Airflow DAG (wiring only)
ingestion/            config, schemas, synthetic data generator, idempotent loader
pipeline/             steps shared by CLI and Airflow, run tracking, optional S3 export
quality/              quality rules, severity model, Markdown report
transformations/dbt_project/   Silver and Gold models, tests, docs
sql/init/             idempotent database setup;  sql/analytics/  business queries
tests/  docs/  data/sample/  reports/  scripts/  .github/workflows/
```

`ingestion/`, `quality/` and `pipeline/` are three small packages instead of one `ingestion/` folder because
loading, checking and orchestrating change for different reasons.

## Design decisions

See [docs/architecture.md](docs/architecture.md). Highlights: Bronze stores text so a bad value never breaks a
load; rejects are quarantined, not deleted; Gold is published by atomic schema swap; dbt runs in its own
virtualenv inside the Airflow image; no dataframe library because the work is `COPY` plus SQL.

## Secrets

`.env.example` holds **local development** values only; `.env` is git-ignored. In production, do not use env
files: inject credentials from a secrets manager (AWS Secrets Manager, Vault, or your orchestrator's secret
backend), use a dedicated least-privilege database role per service, and rotate them.

## Validation status (what was actually run)

Run in a Linux sandbox with Python 3.12, PostgreSQL 16, dbt-core 1.11.16 and Apache Airflow 2.10.5:

- `pytest`: 28 passed (loader, quality rules, generator, S3 stub, end-to-end pipeline with exact expected values,
  idempotent re-run, critical-failure behaviour, analytics SQL). `tests/test_dag.py`: 4 passed in a separate
  Airflow environment (skipped in the main one).
- `ruff check .`: clean. `dbt parse`: clean.
- Full pipeline run twice on the bundled sample via the CLI (second run changed nothing), and the DAG executed
  end-to-end with `airflow dags test` (all 11 tasks succeeded).

**Not validated:** `docker compose` and the Dockerfile (Docker was not available; only the YAML was parsed), the
GitHub Actions workflow (never executed), the optional S3 export against real AWS (only a stub client was
tested), and anything at production scale. This is a portfolio project, **not production-ready** without those
checks, security review and load testing.

## Limitations

- Small, single-node, batch only; no incremental models, no late-arriving data strategy beyond "latest ingestion wins".
- Rejection thresholds are demo values, not tuned.
- Airflow runs with `LocalExecutor` and development credentials.
- Currency is a single unspecified unit; no tax, shipping or refunds accounting.
- No public API ingestion: it would add an external dependency without teaching anything new here.

## Future improvements

Incremental dbt models and snapshots, a dbt docs site and exposures, alerting on critical failures (Slack/e-mail),
schema-drift detection, partitioning for large Bronze tables, a BI dashboard on top of Gold, Terraform for a cloud
deployment.
