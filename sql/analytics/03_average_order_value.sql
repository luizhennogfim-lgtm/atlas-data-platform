-- Average order value (ticket medio) = completed revenue / number of completed orders.
SELECT round(sum(revenue) / sum(orders), 2) AS avg_order_value
FROM gold.daily_revenue;
