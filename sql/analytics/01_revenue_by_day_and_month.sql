-- Revenue per day and per month. Revenue = sum(quantity * unit_price) of COMPLETED orders.
-- Results on the bundled data are demonstrations: the data is synthetic.
SELECT order_date, orders, revenue FROM gold.daily_revenue ORDER BY order_date DESC LIMIT 14;

SELECT month, orders, revenue, mom_growth_pct FROM gold.monthly_revenue ORDER BY month;
