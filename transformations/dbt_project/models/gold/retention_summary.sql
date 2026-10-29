select
    count(*)                                          as customers_with_orders,
    count(*) filter (where is_repeat_customer)        as repeat_customers,
    round(count(*) filter (where is_repeat_customer)::numeric / nullif(count(*), 0), 4) as repeat_purchase_rate
from {{ ref('customer_retention') }}
