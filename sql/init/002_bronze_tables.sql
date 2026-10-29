-- Bronze: raw source values kept as text, exactly as received, plus lineage.
-- _file_id links every row to the file (and run) that brought it in.

CREATE TABLE IF NOT EXISTS bronze.raw_customers (
    customer_id text, email text, full_name text, country text, signup_date text,
    _file_id bigint NOT NULL REFERENCES ops.ingestion_files (file_id),
    _row_number integer NOT NULL,
    _ingested_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS bronze.raw_products (
    product_id text, product_name text, category text, unit_price text,
    _file_id bigint NOT NULL REFERENCES ops.ingestion_files (file_id),
    _row_number integer NOT NULL,
    _ingested_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS bronze.raw_orders (
    order_id text, customer_id text, order_date text, status text,
    _file_id bigint NOT NULL REFERENCES ops.ingestion_files (file_id),
    _row_number integer NOT NULL,
    _ingested_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS bronze.raw_order_items (
    order_item_id text, order_id text, product_id text, quantity text, unit_price text,
    _file_id bigint NOT NULL REFERENCES ops.ingestion_files (file_id),
    _row_number integer NOT NULL,
    _ingested_at timestamptz NOT NULL DEFAULT now()
);

-- Index on _file_id: lineage lookups and per-file counts in the quality report.
CREATE INDEX IF NOT EXISTS ix_raw_customers_file   ON bronze.raw_customers (_file_id);
CREATE INDEX IF NOT EXISTS ix_raw_products_file    ON bronze.raw_products (_file_id);
CREATE INDEX IF NOT EXISTS ix_raw_orders_file      ON bronze.raw_orders (_file_id);
CREATE INDEX IF NOT EXISTS ix_raw_order_items_file ON bronze.raw_order_items (_file_id);
