select
    c.customer_id, c.email, c.full_name, c.country, c.signup_date,
    min(o.order_date) filter (where o.is_revenue) as first_order_date,
    max(o.order_date) filter (where o.is_revenue) as last_order_date,
    count(o.order_id) filter (where o.is_revenue) as completed_orders
from {{ ref('customers') }} c
left join {{ ref('fct_orders') }} o on o.customer_id = c.customer_id
group by c.customer_id, c.email, c.full_name, c.country, c.signup_date
