{# Revenue counts COMPLETED orders only. Cancelled and returned orders are excluded. #}
select
    order_date,
    count(distinct order_id)                                   as orders,
    sum(quantity)                                              as units,
    sum(line_total)::numeric(14, 2)                            as revenue,
    (sum(line_total) / count(distinct order_id))::numeric(14, 2) as avg_order_value
from {{ ref('fct_order_items') }}
where is_revenue
group by order_date
