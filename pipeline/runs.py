"""Run and step tracking in ops.pipeline_runs / ops.step_runs.

A run is identified by a label (the Airflow run_id, or a timestamp for the CLI). The
label maps deterministically to a UUID, so every task of the same DAG run - each in its
own process - finds the same run without sharing memory.
"""
from __future__ import annotations

import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

_NAMESPACE = uuid.UUID("6f1a2b3c-0000-4000-8000-a71a5da7a000")


def run_id_for(label: str) -> uuid.UUID:
    return uuid.uuid5(_NAMESPACE, label)


def ensure_run(conn: psycopg.Connection, label: str, trigger: str = "cli") -> uuid.UUID:
    run_id = run_id_for(label)
    with conn.transaction():
        conn.execute(
            """INSERT INTO ops.pipeline_runs (run_id, run_label, trigger_source)
               VALUES (%s, %s, %s) ON CONFLICT (run_id) DO NOTHING""",
            (run_id, label, trigger),
        )
    return run_id


def finish_run(conn: psycopg.Connection, label: str, status: str, error: str | None = None) -> None:
    with conn.transaction():
        conn.execute(
            """UPDATE ops.pipeline_runs SET status = %s, finished_at = now(), error_message = %s
               WHERE run_id = %s""",
            (status, error, run_id_for(label)),
        )


@contextmanager
def track_step(conn: psycopg.Connection, label: str, step: str) -> Iterator[None]:
    """Record start, outcome, duration and failure reason of one step."""
    run_id = ensure_run(conn, label)
    with conn.transaction():
        step_id = conn.execute(
            "INSERT INTO ops.step_runs (run_id, step_name, status) VALUES (%s, %s, 'running') RETURNING step_run_id",
            (run_id, step),
        ).fetchone()[0]
    started = time.monotonic()
    status, message = "success", None
    try:
        yield
    except Exception as exc:
        status, message = "failed", str(exc)[:4000]
        raise
    finally:
        # Rolls back any half-finished work from the failed step before recording the outcome.
        if conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
            conn.rollback()
        with conn.transaction():
            conn.execute(
                """UPDATE ops.step_runs SET status = %s, message = %s, finished_at = now(), duration_ms = %s
                   WHERE step_run_id = %s""",
                (status, message, int((time.monotonic() - started) * 1000), step_id),
            )
