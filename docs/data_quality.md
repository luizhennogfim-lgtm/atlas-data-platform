# Data quality: warnings vs. critical failures

| Situation | Severity | Effect on the pipeline |
|---|---|---|
| Required file missing, empty, wrong header, bad encoding, no valid rows | **Critical** | Run fails. Nothing new is published. Previous Gold stays. |
| Share of rejected rows above `ATLAS_CRITICAL_REJECT_RATE` (default 20%) | **Critical** | Same as above. |
| Any dbt test fails (unique, not null, relationships, positive amounts, dates, reconciliation) | **Critical** | Run fails before `publish_gold`. |
| Rejected share between `ATLAS_WARN_REJECT_RATE` (1%) and the critical level | Warning | Pipeline continues; shown in the report. |
| Duplicate keys found | Warning | Duplicates are excluded; run continues. |
| Malformed rows inside an otherwise valid file | Warning (or critical above threshold) | Bad rows logged in `ops.ingestion_rejects`; the rest loads. |

Where to look: `reports/quality_report.md`, `ops.quality_checks`, `ops.step_runs` (duration and failure
message per step), `ops.ingestion_files` (records per source), `ops.pipeline_runs` (history and last success).

Thresholds are starting points chosen for this demo, not tuned values.
