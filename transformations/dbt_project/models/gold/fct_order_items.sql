select
    i.order_item_id, i.order_id, i.product_id,
    o.customer_id, o.order_date, o.status,
    p.category,
    i.quantity, i.unit_price,
    (i.quantity * i.unit_price)::numeric(14, 2) as line_total,
    (o.status = 'completed') as is_revenue
from {{ ref('order_items') }} i
join {{ ref('orders') }} o   on o.order_id = i.order_id
join {{ ref('products') }} p on p.product_id = i.product_id
