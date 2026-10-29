"""End-to-end tests on a tiny deterministic dataset (need PostgreSQL and dbt)."""
from datetime import date
from pathlib import Path

import pytest

from pipeline import steps
from quality.checks import QualityGateError


def q(conn, sql):
    return conn.execute(sql).fetchall()


def test_full_run_computes_expected_indicators(conn, settings):
    steps.run_all("t1", settings)
    assert q(conn, "SELECT order_date, orders, revenue FROM gold.daily_revenue ORDER BY 1") == [
        (date(2026, 1, 10), 1, 20), (date(2026, 1, 20), 2, 40)]
    assert q(conn, "SELECT sum(revenue) / sum(orders) FROM gold.daily_revenue")[0][0] == 20  # average order value
    assert q(conn, "SELECT customers_with_orders, repeat_customers, repeat_purchase_rate FROM gold.retention_summary") == [(2, 1, 0.5)]
    assert q(conn, "SELECT product_id FROM gold.product_performance ORDER BY units_rank LIMIT 1") == [("P2",)]
    assert q(conn, "SELECT revenue FROM gold.monthly_revenue") == [(60,)]


def test_invalid_and_duplicate_rows_are_quarantined_with_reasons(conn, settings):
    steps.run_all("t2", settings)
    got = dict(((e, r), n) for e, r, n in q(conn, "SELECT entity, reason, count(*) FROM silver.rejected_records GROUP BY 1, 2"))
    assert got == {("orders", "orphan_customer"): 1, ("order_items", "orphan_order"): 1,
                   ("order_items", "invalid_quantity"): 1, ("order_items", "duplicate_key"): 1}


def test_rerun_is_idempotent(conn, settings):
    steps.run_all("t3a", settings)
    before = (q(conn, "SELECT count(*) FROM bronze.raw_orders"), q(conn, "SELECT count(*) FROM gold.fct_orders"),
              q(conn, "SELECT sum(revenue) FROM gold.daily_revenue"))
    steps.run_all("t3b", settings)
    after = (q(conn, "SELECT count(*) FROM bronze.raw_orders"), q(conn, "SELECT count(*) FROM gold.fct_orders"),
             q(conn, "SELECT sum(revenue) FROM gold.daily_revenue"))
    assert before == after
    assert q(conn, "SELECT count(*) FROM ops.publications") == [(2,)]


def test_critical_failure_keeps_previous_gold(conn, settings):
    steps.run_all("good", settings)
    (Path(settings.source_dir) / "orders.csv").write_text("wrong,header\n1,2\n")
    with pytest.raises(QualityGateError, match="schema_mismatch"):
        steps.run_all("bad", settings)
    assert q(conn, "SELECT status FROM ops.pipeline_runs WHERE run_label = 'bad'") == [("failed",)]
    assert q(conn, "SELECT count(*) FROM gold.fct_orders") == [(4,)]  # last good Gold is still served
    assert q(conn, "SELECT count(*) FROM ops.publications") == [(1,)]
    assert "schema_mismatch" in q(conn, "SELECT error_message FROM ops.pipeline_runs WHERE run_label = 'bad'")[0][0]


def test_high_reject_rate_blocks_publication(conn, settings):
    from dataclasses import replace
    strict = replace(settings, critical_reject_rate=0.05)
    with pytest.raises(QualityGateError, match="invalid_rows_rate"):
        steps.run_all("strict", strict)
    assert q(conn, "SELECT to_regclass('gold.fct_orders')") == [(None,)]  # nothing was published
    assert q(conn, "SELECT count(*) FROM ops.quality_checks WHERE status = 'fail'")[0][0] >= 1


def test_missing_source_file_fails_early(conn, settings):
    (Path(settings.source_dir) / "products.csv").unlink()
    with pytest.raises(steps.SourceUnavailableError, match="products.csv"):
        steps.run_all("missing", settings)
    assert q(conn, "SELECT count(*) FROM bronze.raw_orders") == [(0,)]


def test_report_lists_run_and_checks(conn, settings):
    path = steps.run_all("rep", settings)
    text = Path(path).read_text()
    assert "rep" in text and "invalid_rows_rate" in text and "Rejected and duplicate records" in text


def test_analytics_queries_run(conn, settings):
    steps.run_all("sql", settings)
    for sql_file in sorted((Path(__file__).parent.parent / "sql" / "analytics").glob("*.sql")):
        for statement in sql_file.read_text().split(";"):
            lines = [ln for ln in statement.splitlines() if not ln.strip().startswith("--")]
            if "".join(lines).strip():
                conn.execute("\n".join(lines)).fetchall()
