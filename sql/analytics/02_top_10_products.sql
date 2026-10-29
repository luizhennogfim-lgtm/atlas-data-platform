-- Ten best-selling products by units (ties broken by product id).
SELECT units_rank, product_id, product_name, category, units_sold, revenue
FROM gold.product_performance
ORDER BY units_rank
LIMIT 10;
