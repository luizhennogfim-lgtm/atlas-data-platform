# Metric definitions and business rules

All metrics come from the `gold` schema. Data in this repository is synthetic: results are demonstrations.

| Metric | Definition | Where |
|---|---|---|
| Revenue | Sum of `quantity * unit_price` of items in **completed** orders. Cancelled and returned orders are excluded. | `daily_revenue`, `monthly_revenue` |
| Orders | Distinct completed orders. | same |
| Average order value (ticket medio) | Completed revenue / completed orders. | `daily_revenue.avg_order_value`, `sql/analytics/03_*` |
| Top products | Units sold in completed orders, ties broken by product id. | `product_performance` |
| Repeat purchase rate | Customers with 2+ completed orders / customers with 1+ completed orders. | `retention_summary` |
| Growth (product, category) | (revenue of last 90 days - revenue of the 90 days before) / revenue of the 90 days before. The window ends at the latest order date in the data, not at today's date, so results are reproducible. `NULL` when the prior period has no revenue. | `product_growth`, `category_growth` |
| Month-over-month growth | Change in monthly revenue vs. previous month, in %. | `monthly_revenue` |
| Invalid orders | Orders rejected in Silver for any reason except duplicate key. | `silver.rejected_records`, `sql/analytics/06_*` |
| Last update | `max(published_at)` of `ops.publications`; `gold.data_freshness` has the build time and latest order date. | `sql/analytics/07_*` |

## Validation rules (Silver)

A row is rejected when: the key is missing; the key is a duplicate (latest ingestion wins); a required field is
missing; email is malformed; a date is not a real calendar date or lies in the future; a price is not a number
or is <= 0; a quantity is not an integer or is <= 0; status is not completed / cancelled / returned; an order
references an unknown customer; an order date precedes the customer's signup date; an item references an unknown
order or product.

Rejections **cascade by design**: if an order is rejected, its items become `orphan_order`. That is why
`order_items` shows a higher rejection rate than the other entities.
