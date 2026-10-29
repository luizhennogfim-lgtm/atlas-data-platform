{{ config(materialized='view') }}
{# Validation view: every Bronze customer row, de-duplicated and tagged with a reject_reason (NULL = valid). #}
with src as (
    select
        _file_id, _row_number, _ingested_at,
        nullif(btrim(customer_id), '')   as customer_id,
        nullif(btrim(email), '')         as email_raw,
        nullif(btrim(full_name), '')     as full_name,
        upper(nullif(btrim(country), '')) as country,
        ops.safe_date(signup_date)       as signup_date
    from {{ source('bronze', 'raw_customers') }}
),
ranked as (
    select *,
        row_number() over (
            partition by customer_id
            order by _ingested_at desc, _file_id desc, _row_number desc
        ) as rn
    from src
)
select
    customer_id, lower(email_raw) as email, full_name, country, signup_date,
    _file_id, _row_number, _ingested_at,
    case
        when customer_id is null then 'missing_key'
        when rn > 1 then 'duplicate_key'
        when email_raw is null or email_raw !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' then 'invalid_email'
        when signup_date is null then 'invalid_signup_date'
        when signup_date > current_date then 'future_signup_date'
    end as reject_reason
from ranked
