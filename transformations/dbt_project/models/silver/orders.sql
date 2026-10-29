select order_id, customer_id, order_date, status, _file_id, _ingested_at
from {{ ref('val_orders') }}
where reject_reason is null
