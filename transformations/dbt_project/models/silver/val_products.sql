{{ config(materialized='view') }}
with src as (
    select
        _file_id, _row_number, _ingested_at,
        nullif(btrim(product_id), '')   as product_id,
        nullif(btrim(product_name), '') as product_name,
        nullif(btrim(category), '')     as category,
        ops.safe_numeric(unit_price)    as unit_price
    from {{ source('bronze', 'raw_products') }}
),
ranked as (
    select *,
        row_number() over (
            partition by product_id
            order by _ingested_at desc, _file_id desc, _row_number desc
        ) as rn
    from src
)
select
    product_id, product_name, category, unit_price,
    _file_id, _row_number, _ingested_at,
    case
        when product_id is null then 'missing_key'
        when rn > 1 then 'duplicate_key'
        when product_name is null then 'missing_product_name'
        when category is null then 'missing_category'
        when unit_price is null or unit_price <= 0 then 'invalid_unit_price'
    end as reject_reason
from ranked
