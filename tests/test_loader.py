"""Ingestion tests (need PostgreSQL)."""
from ingestion.loader import ingest_file
from ingestion.schemas import ENTITIES

CUSTOMERS = ENTITIES["customers"]


def _count(conn, table):
    return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def test_loads_rows_with_lineage(conn, tiny_source):
    result = ingest_file(conn, CUSTOMERS, tiny_source / "customers.csv")
    assert (result.status, result.rows_loaded) == ("loaded", 3)
    row = conn.execute("SELECT _file_id, _row_number, _ingested_at FROM bronze.raw_customers ORDER BY _row_number LIMIT 1").fetchone()
    assert row[0] == result.file_id and row[1] == 2 and row[2] is not None


def test_same_file_twice_does_not_duplicate(conn, tiny_source):
    first = ingest_file(conn, CUSTOMERS, tiny_source / "customers.csv")
    second = ingest_file(conn, CUSTOMERS, tiny_source / "customers.csv")
    assert second.status == "skipped" and second.file_id == first.file_id
    assert _count(conn, "bronze.raw_customers") == 3


def test_changed_file_is_a_new_batch(conn, tiny_source):
    ingest_file(conn, CUSTOMERS, tiny_source / "customers.csv")
    with (tiny_source / "customers.csv").open("a") as fh:
        fh.write("C4,c4@example.com,Dani Four,BR,2025-12-20\n")
    assert ingest_file(conn, CUSTOMERS, tiny_source / "customers.csv").status == "loaded"
    assert _count(conn, "bronze.raw_customers") == 7  # raw history is kept; Silver de-duplicates


def test_missing_file_is_rejected_and_logged(conn, tiny_source):
    result = ingest_file(conn, CUSTOMERS, tiny_source / "nope.csv")
    assert result.status == "rejected" and result.message == "file_missing"
    assert conn.execute("SELECT count(*) FROM ops.ingestion_files WHERE status = 'rejected'").fetchone()[0] == 1


def test_empty_file_is_rejected(conn, tiny_source):
    (tiny_source / "customers.csv").write_text("")
    assert ingest_file(conn, CUSTOMERS, tiny_source / "customers.csv").message == "empty_file"
    assert _count(conn, "bronze.raw_customers") == 0


def test_header_only_file_is_rejected(conn, tiny_source):
    (tiny_source / "customers.csv").write_text("customer_id,email,full_name,country,signup_date\n")
    assert ingest_file(conn, CUSTOMERS, tiny_source / "customers.csv").message == "no_data_rows"


def test_wrong_header_is_rejected(conn, tiny_source):
    (tiny_source / "customers.csv").write_text("id,mail\n1,a@b.c\n")
    result = ingest_file(conn, CUSTOMERS, tiny_source / "customers.csv")
    assert result.status == "rejected" and "schema_mismatch" in result.message
    assert _count(conn, "bronze.raw_customers") == 0


def test_malformed_rows_are_logged_and_good_rows_load(conn, tiny_source):
    (tiny_source / "customers.csv").write_text(
        "customer_id,email,full_name,country,signup_date\nC1,a@b.co,Ana,BR,2025-01-01\nC2,only,three\n")
    result = ingest_file(conn, CUSTOMERS, tiny_source / "customers.csv")
    assert (result.rows_loaded, result.rows_malformed) == (1, 1)
    assert conn.execute("SELECT reason FROM ops.ingestion_rejects").fetchone()[0] == "wrong_field_count"


def test_invalid_encoding_is_rejected(conn, tiny_source):
    (tiny_source / "customers.csv").write_bytes(b"customer_id,email,full_name,country,signup_date\nC1,a@b.co,\xff\xfe,BR,2025-01-01\n")
    assert "invalid_encoding" in ingest_file(conn, CUSTOMERS, tiny_source / "customers.csv").message


def test_column_order_does_not_matter(conn, tiny_source):
    (tiny_source / "customers.csv").write_text(
        "email,customer_id,signup_date,country,full_name\na@b.co,C9,2025-01-01,BR,Ana\n")
    ingest_file(conn, CUSTOMERS, tiny_source / "customers.csv")
    assert conn.execute("SELECT customer_id, email FROM bronze.raw_customers").fetchone() == ("C9", "a@b.co")
