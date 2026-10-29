-- Daily revenue must equal the sum of completed line items (no revenue lost or invented).
select 1
from (
    select
        (select coalesce(sum(revenue), 0) from {{ ref('daily_revenue') }}) as daily_total,
        (select coalesce(sum(line_total), 0) from {{ ref('fct_order_items') }} where is_revenue) as item_total
) t
where t.daily_total <> t.item_total
