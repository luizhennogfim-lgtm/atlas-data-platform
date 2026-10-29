"""Idempotent CSV -> Bronze loader.

Rules:
  * A file is identified by (entity, SHA-256 of its bytes). Loading the same content
    twice is a no-op ("skipped"), so re-running a pipeline never duplicates Bronze rows.
  * Each file is loaded in ONE transaction: it is fully loaded or not at all.
  * Whole-file problems (missing, empty, bad header, bad encoding) reject the file and are
    logged in ops.ingestion_files. Row-level problems (wrong field count) are logged in
    ops.ingestion_rejects and the remaining rows still load.
  * Values are stored as text, untouched. Typing and validation happen in Silver.
"""
from __future__ import annotations

import csv
import hashlib
import io
import uuid
from dataclasses import dataclass
from pathlib import Path

import psycopg

from .schemas import ENTITIES, EntitySpec


@dataclass
class IngestResult:
    entity: str
    status: str  # loaded | skipped | rejected
    file_id: int | None = None
    rows_read: int = 0
    rows_loaded: int = 0
    rows_malformed: int = 0
    message: str = ""


def _log_rejected_file(conn: psycopg.Connection, run_id: uuid.UUID | None, spec: EntitySpec,
                       path: Path, sha: str | None, message: str) -> IngestResult:
    with conn.transaction():
        conn.execute(
            """INSERT INTO ops.ingestion_files
               (run_id, entity, source_name, file_sha256, status, error_message)
               VALUES (%s, %s, %s, %s, 'rejected', %s)""",
            (run_id, spec.name, path.name, sha, message),
        )
    return IngestResult(spec.name, "rejected", message=message)


def ingest_file(conn: psycopg.Connection, spec: EntitySpec, path: Path,
                run_id: uuid.UUID | None = None) -> IngestResult:
    if not path.is_file():
        return _log_rejected_file(conn, run_id, spec, path, None, "file_missing")

    raw = path.read_bytes()
    if not raw.strip():
        return _log_rejected_file(conn, run_id, spec, path, None, "empty_file")
    sha = hashlib.sha256(raw).hexdigest()

    already = conn.execute(
        "SELECT file_id FROM ops.ingestion_files WHERE entity = %s AND file_sha256 = %s AND status = 'loaded'",
        (spec.name, sha),
    ).fetchone()
    if already:
        return IngestResult(spec.name, "skipped", file_id=already[0],
                            message="same content already loaded (idempotent no-op)")

    try:
        text = raw.decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(text, newline="")))
    except UnicodeDecodeError:
        return _log_rejected_file(conn, run_id, spec, path, sha, "invalid_encoding (expected UTF-8)")
    except csv.Error as exc:
        return _log_rejected_file(conn, run_id, spec, path, sha, f"malformed_csv: {exc}")

    header = [h.strip() for h in rows[0]]
    missing, unexpected = set(spec.columns) - set(header), set(header) - set(spec.columns)
    if missing or unexpected or len(set(header)) != len(header):
        msg = f"schema_mismatch: missing={sorted(missing)} unexpected={sorted(unexpected)}"
        return _log_rejected_file(conn, run_id, spec, path, sha, msg)

    positions = [header.index(col) for col in spec.columns]
    good: list[tuple[int, list[str]]] = []
    bad: list[tuple[int, str]] = []
    data_rows = 0
    for line_no, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue  # blank line
        data_rows += 1
        if len(row) != len(header):
            bad.append((line_no, ",".join(row)[:2000]))
        else:
            good.append((line_no, [row[p] for p in positions]))

    if data_rows == 0:
        return _log_rejected_file(conn, run_id, spec, path, sha, "no_data_rows")
    if not good:
        return _log_rejected_file(conn, run_id, spec, path, sha, "all_rows_malformed")

    columns = ", ".join(spec.columns)
    with conn.transaction():
        file_id = conn.execute(
            """INSERT INTO ops.ingestion_files
               (run_id, entity, source_name, file_sha256, status, rows_read, rows_loaded, rows_malformed)
               VALUES (%s, %s, %s, %s, 'loaded', %s, %s, %s) RETURNING file_id""",
            (run_id, spec.name, path.name, sha, data_rows, len(good), len(bad)),
        ).fetchone()[0]
        with conn.cursor() as cur:
            with cur.copy(f"COPY {spec.table} ({columns}, _file_id, _row_number) FROM STDIN") as copy:
                for line_no, values in good:
                    copy.write_row([*values, file_id, line_no])
            for line_no, raw_line in bad:
                cur.execute(
                    "INSERT INTO ops.ingestion_rejects (file_id, row_number, reason, raw_line) "
                    "VALUES (%s, %s, 'wrong_field_count', %s)",
                    (file_id, line_no, raw_line),
                )
    return IngestResult(spec.name, "loaded", file_id, data_rows, len(good), len(bad))


def ingest_all(conn: psycopg.Connection, source_dir: Path,
               run_id: uuid.UUID | None = None) -> list[IngestResult]:
    """Load every expected file. One bad file never blocks the others."""
    return [ingest_file(conn, spec, source_dir / spec.filename, run_id) for spec in ENTITIES.values()]
