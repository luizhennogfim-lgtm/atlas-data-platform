"""Quality checks.

Severity model:
  * WARNING  - something looks off (for example 1-20% of rows rejected). The pipeline
               continues and the warning is shown in the quality report.
  * CRITICAL - results would be unreliable (required file missing/invalid, no valid rows,
               more than the critical share rejected). The quality gate raises
               QualityGateError and Gold is NOT published; the previous Gold stays.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import psycopg

from ingestion.schemas import ENTITIES


class QualityGateError(RuntimeError):
    """Raised when at least one critical check failed."""


@dataclass(frozen=True)
class CheckResult:
    check_name: str
    entity: str | None
    severity: str  # warning | critical
    status: str  # pass | warn | fail
    observed: float | None = None
    threshold: float | None = None
    details: str = ""


def rate_check(name: str, entity: str, bad: int, total: int, warn_at: float, critical_at: float) -> CheckResult:
    """Classify a rejection rate against the warning and critical thresholds."""
    rate = bad / total if total else 1.0
    if total == 0 or rate > critical_at:
        return CheckResult(name, entity, "critical", "fail", rate, critical_at, f"{bad} of {total} rows")
    if rate > warn_at:
        return CheckResult(name, entity, "warning", "warn", rate, warn_at, f"{bad} of {total} rows")
    return CheckResult(name, entity, "warning", "pass", rate, warn_at, f"{bad} of {total} rows")


def evaluate_ingestion(conn: psycopg.Connection, run_id: uuid.UUID, warn_at: float, critical_at: float) -> list[CheckResult]:
    """Checks on this run's file loads. A file loaded by an earlier run (same content) is fine."""
    results: list[CheckResult] = []
    for entity in ENTITIES:
        row = conn.execute(
            """SELECT status, rows_read, rows_malformed, error_message FROM ops.ingestion_files
               WHERE entity = %s AND run_id = %s ORDER BY file_id DESC LIMIT 1""",
            (entity, run_id),
        ).fetchone()
        loaded_before = conn.execute(
            "SELECT 1 FROM ops.ingestion_files WHERE entity = %s AND status = 'loaded' LIMIT 1", (entity,)
        ).fetchone()
        if row and row[0] == "rejected":
            results.append(CheckResult("source_file_loaded", entity, "critical", "fail", details=row[3] or ""))
            continue
        if not row and not loaded_before:
            results.append(CheckResult("source_file_loaded", entity, "critical", "fail", details="no file was loaded"))
            continue
        results.append(CheckResult("source_file_loaded", entity, "critical", "pass",
                                   details="loaded" if row else "already loaded earlier (idempotent skip)"))
        if row:
            results.append(rate_check("malformed_rows_rate", entity, row[2], row[1], warn_at, critical_at))
    return results


def evaluate_silver(conn: psycopg.Connection, warn_at: float, critical_at: float) -> list[CheckResult]:
    """Checks on Silver: how many Bronze rows became valid, duplicate or invalid."""
    results: list[CheckResult] = []
    for entity, spec in ENTITIES.items():
        bronze = conn.execute(f"SELECT count(*) FROM {spec.table}").fetchone()[0]
        dup, invalid = conn.execute(
            """SELECT count(*) FILTER (WHERE reason = 'duplicate_key'),
                      count(*) FILTER (WHERE reason <> 'duplicate_key')
               FROM silver.rejected_records WHERE entity = %s""",
            (entity,),
        ).fetchone()
        valid = bronze - dup - invalid
        results.append(CheckResult("valid_rows_present", entity, "critical", "pass" if valid > 0 else "fail",
                                   float(valid), 1.0, f"{valid} valid rows"))
        results.append(rate_check("invalid_rows_rate", entity, invalid, bronze, warn_at, critical_at))
        results.append(CheckResult("duplicates_found", entity, "warning", "warn" if dup else "pass",
                                   float(dup), 0.0, f"{dup} duplicate rows excluded"))
    return results


def record(conn: psycopg.Connection, run_id: uuid.UUID, results: list[CheckResult]) -> None:
    with conn.transaction():
        for r in results:
            conn.execute(
                """INSERT INTO ops.quality_checks
                   (run_id, check_name, entity, severity, status, observed, threshold, details)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (run_id, r.check_name, r.entity, r.severity, r.status, r.observed, r.threshold, r.details),
            )


def gate(results: list[CheckResult]) -> None:
    failed = [r for r in results if r.status == "fail"]
    if failed:
        summary = "; ".join(f"{r.check_name}[{r.entity}]: {r.details}" for r in failed)
        raise QualityGateError(f"Critical quality checks failed: {summary}")
