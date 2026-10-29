"""Pipeline steps. Each step is a plain function, so the CLI and Airflow share the same code.

Every step opens its own connection and is safe to retry (ingestion is idempotent, dbt
models are rebuilt from scratch, publish is one transaction).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import psycopg

from ingestion.config import Settings, get_settings
from ingestion.db import apply_migrations
from ingestion.loader import ingest_all
from ingestion.schemas import ENTITIES
from quality import checks
from quality.report import write_report

from .runs import ensure_run, finish_run, run_id_for, track_step

CANDIDATE_SCHEMA = "gold_candidate"
LIVE_SCHEMA = "gold"
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


class SourceUnavailableError(RuntimeError):
    """A required source file is missing or empty (critical)."""


class DbtError(RuntimeError):
    """A dbt command failed; the message carries the tail of dbt's output."""


def _connect(settings: Settings) -> psycopg.Connection:
    return psycopg.connect(settings.dsn, autocommit=True)


def init_database(settings: Settings | None = None) -> list[str]:
    settings = settings or get_settings()
    with _connect(settings) as conn:
        return apply_migrations(conn, settings.sql_init_dir)


def check_sources(label: str, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    with _connect(settings) as conn, track_step(conn, label, "check_sources"):
        problems = []
        for spec in ENTITIES.values():
            path = settings.source_dir / spec.filename
            if not path.is_file():
                problems.append(f"{spec.filename}: missing")
            elif path.stat().st_size == 0:
                problems.append(f"{spec.filename}: empty")
        if problems:
            raise SourceUnavailableError("; ".join(problems))


def ingest(label: str, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    with _connect(settings) as conn, track_step(conn, label, "ingest"):
        ingest_all(conn, settings.source_dir, run_id_for(label))


def validate_bronze(label: str, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    with _connect(settings) as conn, track_step(conn, label, "validate_bronze"):
        results = checks.evaluate_ingestion(conn, run_id_for(label), settings.warn_reject_rate,
                                            settings.critical_reject_rate)
        checks.record(conn, run_id_for(label), results)
        checks.gate(results)


def validate_silver(label: str, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    with _connect(settings) as conn, track_step(conn, label, "validate_silver"):
        results = checks.evaluate_silver(conn, settings.warn_reject_rate, settings.critical_reject_rate)
        checks.record(conn, run_id_for(label), results)
        checks.gate(results)


def _dbt(settings: Settings, command: str, select: str, gold_schema: str = LIVE_SCHEMA) -> None:
    work = settings.reports_dir / "dbt"
    work.mkdir(parents=True, exist_ok=True)
    project = str(settings.dbt_project_dir)
    cmd = [settings.dbt_bin, "--no-use-colors", command, "--project-dir", project, "--profiles-dir", project,
           "--select", select, "--vars", json.dumps({"gold_schema": gold_schema})]
    env = {**os.environ, **settings.dbt_env(), "DBT_TARGET_PATH": str(work / "target"),
           "DBT_LOG_PATH": str(work / "logs")}
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
    if proc.returncode != 0:
        tail = "\n".join(_ANSI.sub("", proc.stdout).splitlines()[-25:])
        raise DbtError(f"dbt {command} {select} failed (exit {proc.returncode}):\n{tail}")


def dbt_step(label: str, name: str, settings: Settings | None = None) -> None:
    """name: silver_run | silver_test | gold_run | gold_test (Gold is built in a candidate schema)."""
    settings = settings or get_settings()
    layer, command = name.split("_")
    schema = CANDIDATE_SCHEMA if layer == "gold" else LIVE_SCHEMA
    with _connect(settings) as conn, track_step(conn, label, f"dbt_{name}"):
        _dbt(settings, command, f"tag:{layer}", gold_schema=schema)


def publish_gold(label: str, settings: Settings | None = None) -> None:
    """Swap the tested candidate schema into place in ONE transaction.

    Consumers either see the old Gold or the new Gold, never a half-built one. The previous
    Gold is derived data (rebuildable from Silver), so it is dropped after the swap.
    """
    settings = settings or get_settings()
    with _connect(settings) as conn, track_step(conn, label, "publish_gold"):
        with conn.transaction():
            if not conn.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name = %s",
                                (CANDIDATE_SCHEMA,)).fetchone():
                raise RuntimeError(f"schema {CANDIDATE_SCHEMA} not found: nothing to publish")
            conn.execute("DROP SCHEMA IF EXISTS gold_previous CASCADE")
            if conn.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name = %s",
                            (LIVE_SCHEMA,)).fetchone():
                conn.execute(f"ALTER SCHEMA {LIVE_SCHEMA} RENAME TO gold_previous")
            conn.execute(f"ALTER SCHEMA {CANDIDATE_SCHEMA} RENAME TO {LIVE_SCHEMA}")
            conn.execute("DROP SCHEMA IF EXISTS gold_previous CASCADE")
            conn.execute("INSERT INTO ops.publications (run_id) VALUES (%s)", (run_id_for(label),))


def finish(label: str, status: str, error: str | None = None, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    with _connect(settings) as conn:
        ensure_run(conn, label)
        finish_run(conn, label, status, error)
        return write_report(conn, settings.reports_dir, label)


# Order used by the CLI; the Airflow DAG wires the same steps as tasks.
def run_all(label: str, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    init_database(settings)
    with _connect(settings) as conn:
        ensure_run(conn, label)
    try:
        check_sources(label, settings)
        ingest(label, settings)
        validate_bronze(label, settings)
        dbt_step(label, "silver_run", settings)
        dbt_step(label, "silver_test", settings)
        validate_silver(label, settings)
        dbt_step(label, "gold_run", settings)
        dbt_step(label, "gold_test", settings)
        publish_gold(label, settings)
    except Exception as exc:
        finish(label, "failed", str(exc)[:4000], settings)
        raise
    return finish(label, "success", None, settings)
