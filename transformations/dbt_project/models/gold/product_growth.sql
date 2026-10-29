{# Recent window = last 90 days of data; prior window = the 90 days before it.
   The reference date is the latest order date in the data, not today's date,
   so results are reproducible. #}
{% set days = 90 %}
with ref_date as (select max(order_date) as d from {{ ref('fct_order_items') }}),
windowed as (
    select
        i.product_id,
        sum(i.line_total) filter (where i.order_date >  r.d - {{ days }}) as recent_revenue,
        sum(i.line_total) filter (where i.order_date <= r.d - {{ days }}
                                    and i.order_date >  r.d - {{ 2 * days }}) as prior_revenue
    from {{ ref('fct_order_items') }} i cross join ref_date r
    where i.is_revenue
    group by i.product_id
)
select
    p.product_id, p.product_name, p.category,
    coalesce(w.recent_revenue, 0)::numeric(14, 2) as recent_revenue,
    coalesce(w.prior_revenue, 0)::numeric(14, 2)  as prior_revenue,
    case when coalesce(w.prior_revenue, 0) > 0
         then round(100.0 * (coalesce(w.recent_revenue, 0) - w.prior_revenue) / w.prior_revenue, 2)
    end as growth_pct
from {{ ref('dim_products') }} p
left join windowed w on w.product_id = p.product_id
