with monthly as (
    select
        date_trunc('month', order_date)::date as month,
        count(distinct order_id)              as orders,
        sum(line_total)::numeric(14, 2)       as revenue
    from {{ ref('fct_order_items') }}
    where is_revenue
    group by 1
)
select
    month, orders, revenue,
    (revenue / orders)::numeric(14, 2) as avg_order_value,
    round(100.0 * (revenue - lag(revenue) over (order by month))
          / nullif(lag(revenue) over (order by month), 0), 2) as mom_growth_pct
from monthly
