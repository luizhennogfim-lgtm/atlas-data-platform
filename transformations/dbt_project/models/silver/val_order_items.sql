{{ config(materialized='view') }}
with src as (
    select
        _file_id, _row_number, _ingested_at,
        nullif(btrim(order_item_id), '') as order_item_id,
        nullif(btrim(order_id), '')      as order_id,
        nullif(btrim(product_id), '')    as product_id,
        ops.safe_int(quantity)           as quantity,
        ops.safe_numeric(unit_price)     as unit_price
    from {{ source('bronze', 'raw_order_items') }}
),
ranked as (
    select *,
        row_number() over (
            partition by order_item_id
            order by _ingested_at desc, _file_id desc, _row_number desc
        ) as rn
    from src
)
select
    r.order_item_id, r.order_id, r.product_id, r.quantity, r.unit_price,
    r._file_id, r._row_number, r._ingested_at,
    case
        when r.order_item_id is null then 'missing_key'
        when r.rn > 1 then 'duplicate_key'
        when r.quantity is null or r.quantity <= 0 then 'invalid_quantity'
        when r.unit_price is null or r.unit_price <= 0 then 'invalid_unit_price'
        when o.order_id is null then 'orphan_order'
        when p.product_id is null then 'orphan_product'
    end as reject_reason
from ranked r
left join {{ ref('orders') }} o on o.order_id = r.order_id
left join {{ ref('products') }} p on p.product_id = r.product_id
