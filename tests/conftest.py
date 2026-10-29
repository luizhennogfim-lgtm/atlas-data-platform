"""Shared fixtures.

Unit tests need nothing. Integration tests need PostgreSQL (ATLAS_TEST_DSN, database name
must end with "_test" because the fixture resets its schemas) and are skipped otherwise.
The transformation tests also need the `dbt` executable.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import psycopg
import pytest

from ingestion.config import PROJECT_ROOT, Settings
from ingestion.db import apply_migrations

TEST_DSN = os.environ.get("ATLAS_TEST_DSN")

TINY = {
    "customers.csv": """customer_id,email,full_name,country,signup_date
C1,c1@example.com,Ana One,BR,2025-12-01
C2,c2@example.com,Bruno Two,BR,2025-12-01
C3,c3@example.com,Carla Three,US,2025-12-15
""",
    "products.csv": """product_id,product_name,category,unit_price
P1,Lamp,Home,10.00
P2,Novel,Books,5.00
""",
    "orders.csv": """order_id,customer_id,order_date,status
O1,C1,2026-01-10,completed
O2,C1,2026-01-20,completed
O3,C2,2026-01-20,completed
O4,C2,2026-02-05,cancelled
O5,CX,2026-02-01,completed
""",
    "order_items.csv": """order_item_id,order_id,product_id,quantity,unit_price
OI1,O1,P1,2,10.00
OI2,O2,P2,4,5.00
OI3,O3,P1,1,10.00
OI4,O3,P2,2,5.00
OI5,O4,P1,1,10.00
OI6,O5,P1,1,10.00
OI7,O1,P1,0,10.00
OI1,O1,P1,2,10.00
""",
}


@pytest.fixture
def conn():
    if not TEST_DSN:
        pytest.skip("ATLAS_TEST_DSN not set (integration test)")
    c = psycopg.connect(TEST_DSN, autocommit=True)
    dbname = c.info.dbname
    assert dbname.endswith("_test"), f"refusing to reset non-test database {dbname!r}"
    for schema in ("ops", "bronze", "silver", "gold", "gold_candidate", "gold_previous"):
        c.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    apply_migrations(c, PROJECT_ROOT / "sql" / "init")
    yield c
    c.close()


@pytest.fixture
def tiny_source(tmp_path: Path) -> Path:
    src = tmp_path / "source"
    src.mkdir()
    for name, content in TINY.items():
        (src / name).write_text(content, encoding="utf-8")
    return src


@pytest.fixture
def settings(conn, tiny_source, tmp_path) -> Settings:
    if not shutil.which("dbt"):
        pytest.skip("dbt executable not found")
    return Settings(
        dsn=TEST_DSN, source_dir=tiny_source,
        dbt_project_dir=PROJECT_ROOT / "transformations" / "dbt_project",
        dbt_bin="dbt", reports_dir=tmp_path / "reports", sql_init_dir=PROJECT_ROOT / "sql" / "init",
        warn_reject_rate=0.01, critical_reject_rate=0.5,
    )
