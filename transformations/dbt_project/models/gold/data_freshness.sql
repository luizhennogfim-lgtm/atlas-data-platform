select
    now()                                   as built_at,
    (select max(order_date) from {{ ref('fct_orders') }}) as latest_order_date,
    (select count(*) from {{ ref('fct_orders') }})        as orders_in_gold
