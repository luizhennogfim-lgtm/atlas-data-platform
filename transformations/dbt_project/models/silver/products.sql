select product_id, product_name, category, unit_price, _file_id, _ingested_at
from {{ ref('val_products') }}
where reject_reason is null
