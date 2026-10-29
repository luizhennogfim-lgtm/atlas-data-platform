import csv

from ingestion.generate_data import generate


def test_same_seed_same_files(tmp_path):
    generate(tmp_path / "a", seed=7, n_orders=50, n_customers=30, n_products=12)
    generate(tmp_path / "b", seed=7, n_orders=50, n_customers=30, n_products=12)
    for name in ("customers", "products", "orders", "order_items"):
        assert (tmp_path / "a" / f"{name}.csv").read_bytes() == (tmp_path / "b" / f"{name}.csv").read_bytes()


def test_different_seed_changes_data(tmp_path):
    generate(tmp_path / "a", seed=1, n_orders=300, n_customers=60, n_products=20)
    generate(tmp_path / "b", seed=2, n_orders=300, n_customers=60, n_products=20)
    assert (tmp_path / "a" / "orders.csv").read_bytes() != (tmp_path / "b" / "orders.csv").read_bytes()


def test_known_defects_are_present(tmp_path):
    generate(tmp_path, seed=42)
    with (tmp_path / "customers.csv").open(newline="") as fh:
        ids = [r["customer_id"] for r in csv.DictReader(fh)]
    assert "" in ids  # missing key
    assert len(ids) != len(set(ids))  # duplicates
