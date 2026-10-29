"""Database helpers: connections and idempotent initialisation scripts."""
from __future__ import annotations

from pathlib import Path

import psycopg

_BOOTSTRAP = """
CREATE SCHEMA IF NOT EXISTS ops;
CREATE TABLE IF NOT EXISTS ops.schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);
"""


def connect(dsn: str) -> psycopg.Connection:
    return psycopg.connect(dsn)


def apply_migrations(conn: psycopg.Connection, sql_dir: Path) -> list[str]:
    """Apply sql/init/*.sql in order, once each. Never drops or truncates anything."""
    applied: list[str] = []
    with conn.transaction():
        conn.execute(_BOOTSTRAP)
    for path in sorted(sql_dir.glob("*.sql")):
        with conn.transaction():
            done = conn.execute(
                "SELECT 1 FROM ops.schema_migrations WHERE version = %s", (path.name,)
            ).fetchone()
            if done:
                continue
            conn.execute(path.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO ops.schema_migrations (version) VALUES (%s)", (path.name,))
            applied.append(path.name)
    return applied
