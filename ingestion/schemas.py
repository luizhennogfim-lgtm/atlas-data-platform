"""Expected source files: one EntitySpec per CSV and its Bronze table."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EntitySpec:
    name: str
    filename: str
    table: str
    columns: tuple[str, ...]
    key: str


ENTITIES: dict[str, EntitySpec] = {
    spec.name: spec
    for spec in (
        EntitySpec(
            "customers", "customers.csv", "bronze.raw_customers",
            ("customer_id", "email", "full_name", "country", "signup_date"), "customer_id",
        ),
        EntitySpec(
            "products", "products.csv", "bronze.raw_products",
            ("product_id", "product_name", "category", "unit_price"), "product_id",
        ),
        EntitySpec(
            "orders", "orders.csv", "bronze.raw_orders",
            ("order_id", "customer_id", "order_date", "status"), "order_id",
        ),
        EntitySpec(
            "order_items", "order_items.csv", "bronze.raw_order_items",
            ("order_item_id", "order_id", "product_id", "quantity", "unit_price"),
            "order_item_id",
        ),
    )
}
