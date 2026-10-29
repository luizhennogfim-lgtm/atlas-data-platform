select
    p.product_id, p.product_name, p.category,
    coalesce(sum(i.quantity), 0)                    as units_sold,
    coalesce(sum(i.line_total), 0)::numeric(14, 2)  as revenue,
    count(distinct i.order_id)                      as orders,
    rank() over (order by coalesce(sum(i.quantity), 0) desc, p.product_id) as units_rank,
    rank() over (order by coalesce(sum(i.line_total), 0) desc, p.product_id) as revenue_rank
from {{ ref('dim_products') }} p
left join {{ ref('fct_order_items') }} i on i.product_id = p.product_id and i.is_revenue
group by p.product_id, p.product_name, p.category
