-- An order's total must equal the sum of its items.
select o.order_id
from {{ ref('fct_orders') }} o
join (
    select order_id, sum(line_total) as total from {{ ref('fct_order_items') }} group by order_id
) i using (order_id)
where o.order_total <> i.total
