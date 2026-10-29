{# Every Bronze row that did not make it into Silver, with the reason. Quarantine, not deletion. #}
{% set entities = [
    ('customers', 'val_customers', 'customer_id'),
    ('products', 'val_products', 'product_id'),
    ('orders', 'val_orders', 'order_id'),
    ('order_items', 'val_order_items', 'order_item_id'),
] %}
{% for entity, model, key in entities %}
select
    '{{ entity }}'::text as entity,
    {{ key }}::text      as record_key,
    reject_reason        as reason,
    _file_id             as file_id,
    _row_number          as row_number,
    _ingested_at         as ingested_at
from {{ ref(model) }}
where reject_reason is not null
{% if not loop.last %}union all{% endif %}
{% endfor %}
