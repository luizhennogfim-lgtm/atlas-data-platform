select
    o.order_id, o.customer_id, o.order_date, o.status,
    (o.status = 'completed')                         as is_revenue,
    count(i.order_item_id)                           as items_count,
    coalesce(sum(i.quantity), 0)                     as units,
    coalesce(sum(i.line_total), 0)::numeric(14, 2)   as order_total
from {{ ref('orders') }} o
left join {{ ref('fct_order_items') }} i on i.order_id = o.order_id
group by o.order_id, o.customer_id, o.order_date, o.status
