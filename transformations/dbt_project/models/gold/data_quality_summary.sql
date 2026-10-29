{# Per entity: how many Bronze rows arrived, how many reached Silver, and why the rest did not. #}
with bronze as (
    select 'customers'::text as entity, count(*) as bronze_rows from {{ source('bronze', 'raw_customers') }}
    union all select 'products',    count(*) from {{ source('bronze', 'raw_products') }}
    union all select 'orders',      count(*) from {{ source('bronze', 'raw_orders') }}
    union all select 'order_items', count(*) from {{ source('bronze', 'raw_order_items') }}
),
rej as (
    select entity,
           count(*) filter (where reason = 'duplicate_key')  as duplicate_rows,
           count(*) filter (where reason <> 'duplicate_key') as invalid_rows
    from {{ ref('rejected_records') }}
    group by entity
)
select
    b.entity, b.bronze_rows,
    b.bronze_rows - coalesce(r.duplicate_rows, 0) - coalesce(r.invalid_rows, 0) as valid_rows,
    coalesce(r.duplicate_rows, 0) as duplicate_rows,
    coalesce(r.invalid_rows, 0)   as invalid_rows
from bronze b left join rej r using (entity)
