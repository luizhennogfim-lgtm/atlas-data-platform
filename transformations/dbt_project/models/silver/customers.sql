select customer_id, email, full_name, country, signup_date, _file_id, _ingested_at
from {{ ref('val_customers') }}
where reject_reason is null
