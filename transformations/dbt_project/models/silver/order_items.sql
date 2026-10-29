select order_item_id, order_id, product_id, quantity, unit_price, _file_id, _ingested_at
from {{ ref('val_order_items') }}
where reject_reason is null
