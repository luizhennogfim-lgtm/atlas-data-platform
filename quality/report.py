"""Human-readable quality report (Markdown) built from the ops tables."""
from __future__ import annotations

from pathlib import Path

import psycopg


def _table(headers: list[str], rows: list[tuple]) -> str:
    if not rows:
        return "_No data._\n"
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join("" if v is None else str(v) for v in r) + " |" for r in rows]
    return "\n".join(lines) + "\n"


def build_report(conn: psycopg.Connection, label: str | None = None) -> str:
    if label:
        run = conn.execute("SELECT run_id, run_label, status, started_at, finished_at, error_message "
                           "FROM ops.pipeline_runs WHERE run_label = %s", (label,)).fetchone()
    else:
        run = conn.execute("SELECT run_id, run_label, status, started_at, finished_at, error_message "
                           "FROM ops.pipeline_runs ORDER BY started_at DESC LIMIT 1").fetchone()
    out = ["# Atlas data quality report", "",
           "_Generated from the ops tables. Data is synthetic (demonstration only)._", ""]
    last_ok = conn.execute("SELECT max(finished_at) FROM ops.pipeline_runs WHERE status = 'success'").fetchone()[0]
    out += [f"Last successful run finished at: **{last_ok or 'never'}**", ""]
    if not run:
        return "\n".join(out + ["No pipeline run recorded yet.", ""])
    run_id = run[0]
    out += ["## Latest run", "", _table(["run", "status", "started", "finished", "error"], [run[1:]]), "",
            "## Steps", "",
            _table(["step", "status", "duration_ms", "message"], conn.execute(
                "SELECT step_name, status, duration_ms, left(coalesce(message, ''), 120) "
                "FROM ops.step_runs WHERE run_id = %s ORDER BY step_run_id", (run_id,)).fetchall()), "",
            "## Quality checks", "",
            "Warnings never stop the pipeline. A critical failure stops it before Gold is published.", "",
            _table(["check", "entity", "severity", "status", "observed", "details"], conn.execute(
                "SELECT check_name, entity, severity, status, round(observed, 4), details "
                "FROM ops.quality_checks WHERE run_id = %s ORDER BY check_id", (run_id,)).fetchall()), "",
            "## Records per source file", "",
            _table(["entity", "file", "status", "rows_read", "rows_loaded", "malformed", "error"], conn.execute(
                "SELECT entity, source_name, status, rows_read, rows_loaded, rows_malformed, error_message "
                "FROM ops.ingestion_files ORDER BY file_id DESC LIMIT 12").fetchall()), ""]
    if conn.execute("SELECT to_regclass('silver.rejected_records')").fetchone()[0]:
        out += ["## Rejected and duplicate records (Silver quarantine)", "",
                _table(["entity", "reason", "rows"], conn.execute(
                    "SELECT entity, reason, count(*) FROM silver.rejected_records GROUP BY 1, 2 ORDER BY 1, 3 DESC").fetchall()), ""]
    out += ["## Run history (last 10)", "",
            _table(["run", "status", "started", "finished"], conn.execute(
                "SELECT run_label, status, started_at, finished_at FROM ops.pipeline_runs "
                "ORDER BY started_at DESC LIMIT 10").fetchall()), ""]
    return "\n".join(out)


def write_report(conn: psycopg.Connection, reports_dir: Path, label: str | None = None) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / "quality_report.md"
    path.write_text(build_report(conn, label), encoding="utf-8")
    return path
