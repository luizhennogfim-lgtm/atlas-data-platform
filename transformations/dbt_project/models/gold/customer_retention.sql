select
    customer_id,
    completed_orders,
    first_order_date,
    last_order_date,
    (completed_orders >= 2) as is_repeat_customer
from {{ ref('dim_customers') }}
where completed_orders >= 1
