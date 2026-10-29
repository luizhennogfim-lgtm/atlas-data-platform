{% set days = 90 %}
with ref_date as (select max(order_date) as d from {{ ref('fct_order_items') }}),
windowed as (
    select
        i.category,
        sum(i.line_total) filter (where i.order_date >  r.d - {{ days }}) as recent_revenue,
        sum(i.line_total) filter (where i.order_date <= r.d - {{ days }}
                                    and i.order_date >  r.d - {{ 2 * days }}) as prior_revenue
    from {{ ref('fct_order_items') }} i cross join ref_date r
    where i.is_revenue
    group by i.category
)
select
    category,
    coalesce(recent_revenue, 0)::numeric(14, 2) as recent_revenue,
    coalesce(prior_revenue, 0)::numeric(14, 2)  as prior_revenue,
    case when coalesce(prior_revenue, 0) > 0
         then round(100.0 * (coalesce(recent_revenue, 0) - prior_revenue) / prior_revenue, 2)
    end as growth_pct
from windowed
