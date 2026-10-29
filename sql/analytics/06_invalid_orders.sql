-- Orders that were rejected (invalid) and why. Duplicates are reported separately.
SELECT reason, count(*) AS orders
FROM silver.rejected_records
WHERE entity = 'orders' AND reason <> 'duplicate_key'
GROUP BY reason
ORDER BY orders DESC;

SELECT entity, bronze_rows, valid_rows, duplicate_rows, invalid_rows FROM gold.data_quality_summary;
