select product_id, product_name, category, unit_price as list_price
from {{ ref('products') }}
