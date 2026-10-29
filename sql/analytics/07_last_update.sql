-- When was the analytical data last published, and what period does it cover?
SELECT max(published_at) AS last_published_at FROM ops.publications;
SELECT built_at, latest_order_date, orders_in_gold FROM gold.data_freshness;
