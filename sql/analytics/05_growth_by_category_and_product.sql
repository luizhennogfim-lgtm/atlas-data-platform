-- Revenue of the last 90 days of data vs. the 90 days before it.
SELECT category, prior_revenue, recent_revenue, growth_pct
FROM gold.category_growth
ORDER BY growth_pct DESC NULLS LAST;

SELECT product_id, product_name, prior_revenue, recent_revenue, growth_pct
FROM gold.product_growth
WHERE growth_pct IS NOT NULL
ORDER BY growth_pct DESC
LIMIT 10;
