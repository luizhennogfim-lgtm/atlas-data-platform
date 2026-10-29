-- Date consistency: no order may precede the customer's signup date.
select o.order_id
from {{ ref('orders') }} o
join {{ ref('customers') }} c using (customer_id)
where o.order_date < c.signup_date
