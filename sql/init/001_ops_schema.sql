-- Operational metadata: runs, steps, ingestion log, quality results.
-- Safe to re-run: everything is CREATE ... IF NOT EXISTS (nothing is dropped).

CREATE SCHEMA IF NOT EXISTS ops;
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;

CREATE TABLE IF NOT EXISTS ops.pipeline_runs (
    run_id        uuid PRIMARY KEY,
    run_label     text        NOT NULL UNIQUE,   -- Airflow run_id or CLI timestamp
    trigger_source text       NOT NULL DEFAULT 'cli',
    status        text        NOT NULL DEFAULT 'running'
                  CHECK (status IN ('running', 'success', 'failed')),
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    error_message text
);

CREATE TABLE IF NOT EXISTS ops.step_runs (
    step_run_id  bigserial PRIMARY KEY,
    run_id       uuid        NOT NULL REFERENCES ops.pipeline_runs (run_id),
    step_name    text        NOT NULL,
    status       text        NOT NULL CHECK (status IN ('running', 'success', 'failed')),
    started_at   timestamptz NOT NULL DEFAULT now(),
    finished_at  timestamptz,
    duration_ms  integer,
    message      text
);
-- Index: the run report reads all steps of one run.
CREATE INDEX IF NOT EXISTS ix_step_runs_run_id ON ops.step_runs (run_id);

CREATE TABLE IF NOT EXISTS ops.ingestion_files (
    file_id        bigserial PRIMARY KEY,
    run_id         uuid REFERENCES ops.pipeline_runs (run_id),
    entity         text        NOT NULL,
    source_name    text        NOT NULL,         -- file name (data origin)
    file_sha256    char(64),
    status         text        NOT NULL CHECK (status IN ('loaded', 'rejected')),
    rows_read      integer     NOT NULL DEFAULT 0,
    rows_loaded    integer     NOT NULL DEFAULT 0,
    rows_malformed integer     NOT NULL DEFAULT 0,
    error_message  text,
    ingested_at    timestamptz NOT NULL DEFAULT now()
);
-- Idempotency guard: the same content can be loaded only once per entity.
CREATE UNIQUE INDEX IF NOT EXISTS ux_ingestion_loaded_hash
    ON ops.ingestion_files (entity, file_sha256) WHERE status = 'loaded';

CREATE TABLE IF NOT EXISTS ops.ingestion_rejects (
    reject_id  bigserial PRIMARY KEY,
    file_id    bigint  NOT NULL REFERENCES ops.ingestion_files (file_id),
    row_number integer NOT NULL,
    reason     text    NOT NULL,
    raw_line   text
);

CREATE TABLE IF NOT EXISTS ops.quality_checks (
    check_id   bigserial PRIMARY KEY,
    run_id     uuid        NOT NULL REFERENCES ops.pipeline_runs (run_id),
    check_name text        NOT NULL,
    entity     text,
    severity   text        NOT NULL CHECK (severity IN ('warning', 'critical')),
    status     text        NOT NULL CHECK (status IN ('pass', 'warn', 'fail')),
    observed   numeric,
    threshold  numeric,
    details    text,
    checked_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_quality_checks_run_id ON ops.quality_checks (run_id);

CREATE TABLE IF NOT EXISTS ops.publications (
    publication_id bigserial PRIMARY KEY,
    run_id         uuid        NOT NULL REFERENCES ops.pipeline_runs (run_id),
    published_at   timestamptz NOT NULL DEFAULT now()
);

-- Safe parsers: return NULL instead of raising, so bad text becomes a rejected
-- record rather than a crashed pipeline.
CREATE OR REPLACE FUNCTION ops.safe_date(v text) RETURNS date
LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
    IF v IS NULL OR btrim(v) !~ '^\d{4}-\d{2}-\d{2}$' THEN RETURN NULL; END IF;
    RETURN btrim(v)::date;
EXCEPTION WHEN others THEN
    RETURN NULL;
END $$;

CREATE OR REPLACE FUNCTION ops.safe_numeric(v text) RETURNS numeric
LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
    IF v IS NULL OR btrim(v) !~ '^-?\d{1,12}(\.\d{1,4})?$' THEN RETURN NULL; END IF;
    RETURN btrim(v)::numeric;
EXCEPTION WHEN others THEN
    RETURN NULL;
END $$;

CREATE OR REPLACE FUNCTION ops.safe_int(v text) RETURNS integer
LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
    IF v IS NULL OR btrim(v) !~ '^-?\d{1,9}$' THEN RETURN NULL; END IF;
    RETURN btrim(v)::integer;
EXCEPTION WHEN others THEN
    RETURN NULL;
END $$;
