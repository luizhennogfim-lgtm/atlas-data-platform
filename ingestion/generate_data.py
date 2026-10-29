"""Deterministic synthetic e-commerce data (fictional company, no real people).

The files deliberately contain a small share of bad records (duplicates, invalid
prices, orphan keys, bad dates) so the quality layer has something real to catch.
Everything is driven by a seed: the same seed always produces the same files.
"""
from __future__ import annotations

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

FIRST = ["Ana", "Bruno", "Carla", "Diego", "Elena", "Felipe", "Gabi", "Hugo", "Iris", "Joao",
         "Karen", "Lucas", "Maya", "Nina", "Otavio", "Paula", "Rafa", "Sara", "Tiago", "Vera"]
LAST = ["Silva", "Souza", "Costa", "Lima", "Alves", "Rocha", "Dias", "Melo", "Ramos", "Nunes"]
COUNTRIES = ["BR", "US", "PT", "DE", "MX"]
# category -> (price range, monthly growth factor: >0 grows, <0 shrinks)
CATEGORIES = {
    "Electronics": ((40.0, 600.0), 0.06),
    "Home": ((15.0, 250.0), 0.01),
    "Fashion": ((20.0, 180.0), 0.00),
    "Books": ((8.0, 60.0), -0.02),
    "Sports": ((18.0, 300.0), 0.03),
    "Beauty": ((6.0, 120.0), 0.02),
}


def _write(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def generate(out_dir: Path, seed: int = 42, n_customers: int = 200, n_products: int = 48,
             n_orders: int = 1500, start: date = date(2025, 10, 1), days: int = 365) -> dict[str, int]:
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    customers = []
    for i in range(1, n_customers + 1):
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        signup = start - timedelta(days=rng.randint(30, 600))
        customers.append([f"C{i:04d}", f"customer{i:04d}@example.com", name,
                          rng.choice(COUNTRIES), signup.isoformat()])

    cats = list(CATEGORIES)
    products = []
    for i in range(1, n_products + 1):
        cat = cats[(i - 1) % len(cats)]
        low, high = CATEGORIES[cat][0]
        products.append([f"P{i:03d}", f"{cat} item {i:03d}", cat, f"{rng.uniform(low, high):.2f}"])
    price = {p[0]: p[3] for p in products}
    by_cat: dict[str, list[str]] = {c: [p[0] for p in products if p[2] == c] for c in cats}

    # Repeat buyers: customer weights are skewed so some customers order often.
    weights = [1 / (1 + (i % 17)) for i in range(n_customers)]
    orders, items = [], []
    item_seq = 0
    for o in range(1, n_orders + 1):
        day = rng.randint(0, days - 1)
        month_idx = day // 30
        order_date = start + timedelta(days=day)
        cust = rng.choices(customers, weights=weights)[0]
        status = rng.choices(["completed", "cancelled", "returned"], weights=[86, 8, 6])[0]
        orders.append([f"O{o:06d}", cust[0], order_date.isoformat(), status])
        cat_weights = [max(0.2, 1 + CATEGORIES[c][1] * month_idx) for c in cats]
        for _ in range(rng.choices([1, 2, 3, 4], weights=[45, 30, 17, 8])[0]):
            cat = rng.choices(cats, weights=cat_weights)[0]
            pid = rng.choice(by_cat[cat])
            item_seq += 1
            unit = f"{float(price[pid]) * rng.choice([1.0, 1.0, 0.9]):.2f}"
            items.append([f"OI{item_seq:07d}", f"O{o:06d}", pid, str(rng.randint(1, 4)), unit])

    # ---- deliberate defects (small, known counts; skipped when a table is too small) ----
    def dup(rows: list[list[str]], i: int) -> None:
        if i < len(rows):
            rows.append(rows[i][:])

    def corrupt(rows: list[list[str]], i: int, col: int, value: str) -> None:
        if i < len(rows):
            rows[i][col] = value

    dup(customers, 3)                                  # duplicate row
    dup(customers, 10)                                 # duplicate row
    corrupt(customers, 20, 1, "not-an-email")          # invalid email
    corrupt(customers, 30, 4, "2025-13-45")            # impossible date
    corrupt(customers, 16, 4, "2026-09-25")            # signs up after earlier orders
    customers.append(["", "nokey@example.com", "No Key", "BR", "2025-01-01"])  # missing key
    dup(products, 5)                                   # duplicate row
    corrupt(products, 7, 3, "-9.90")                   # negative price
    corrupt(products, 9, 3, "abc")                     # non-numeric price
    dup(orders, 40)                                    # duplicate row
    dup(orders, 41)                                    # duplicate row
    corrupt(orders, 50, 1, "C9999")                    # orphan customer
    corrupt(orders, 60, 2, "2026-02-30")               # impossible date
    corrupt(orders, 70, 3, "unknown")                  # invalid status
    corrupt(orders, 80, 2, "2030-01-01")               # future date
    dup(items, 100)                                    # duplicate row
    corrupt(items, 200, 3, "0")                        # zero quantity
    corrupt(items, 210, 3, "-2")                       # negative quantity
    corrupt(items, 220, 2, "P999")                     # orphan product
    corrupt(items, 230, 1, "O999999")                  # orphan order
    corrupt(items, 240, 4, "-5.00")                    # negative price
    corrupt(items, 250, 4, "")                         # missing price

    rng.shuffle(customers)
    rng.shuffle(orders)
    _write(out_dir / "customers.csv", ["customer_id", "email", "full_name", "country", "signup_date"], customers)
    _write(out_dir / "products.csv", ["product_id", "product_name", "category", "unit_price"], products)
    _write(out_dir / "orders.csv", ["order_id", "customer_id", "order_date", "status"], orders)
    _write(out_dir / "order_items.csv", ["order_item_id", "order_id", "product_id", "quantity", "unit_price"], items)
    return {"customers": len(customers), "products": len(products),
            "orders": len(orders), "order_items": len(items)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic Atlas source files")
    parser.add_argument("--out", type=Path, default=Path("data/sample"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(generate(args.out, seed=args.seed))


if __name__ == "__main__":
    main()
