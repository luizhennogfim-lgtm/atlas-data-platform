{{ config(materialized='view') }}
with src as (
    select
        _file_id, _row_number, _ingested_at,
        nullif(btrim(order_id), '')    as order_id,
        nullif(btrim(customer_id), '') as customer_id,
        ops.safe_date(order_date)      as order_date,
        lower(nullif(btrim(status), '')) as status
    from {{ source('bronze', 'raw_orders') }}
),
ranked as (
    select *,
        row_number() over (
            partition by order_id
            order by _ingested_at desc, _file_id desc, _row_number desc
        ) as rn
    from src
)
select
    r.order_id, r.customer_id, r.order_date, r.status,
    r._file_id, r._row_number, r._ingested_at,
    case
        when r.order_id is null then 'missing_key'
        when r.rn > 1 then 'duplicate_key'
        when r.customer_id is null then 'missing_customer_id'
        when r.order_date is null then 'invalid_order_date'
        when r.order_date > current_date then 'future_order_date'
        when r.status is null or r.status not in ('completed', 'cancelled', 'returned') then 'invalid_status'
        when c.customer_id is null then 'orphan_customer'
        when r.order_date < c.signup_date then 'order_before_signup'
    end as reject_reason
from ranked r
left join {{ ref('customers') }} c on c.customer_id = r.customer_id
