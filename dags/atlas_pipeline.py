"""Airflow DAG for the Atlas pipeline.

The DAG only wires tasks and policies (retries, timeouts, trigger rules). All logic lives in
pipeline/steps.py, so it is unit-testable and also runnable from the CLI.

  init_db -> check_sources -> ingest -> validate_bronze -> dbt_silver_run -> dbt_silver_test
          -> validate_silver -> dbt_gold_run -> dbt_gold_test -> publish_gold -> record_success
  (any failure) -> record_failure

Gold is built in a candidate schema and swapped in only by publish_gold, after every
test and quality gate passed. A critical failure therefore leaves the previous Gold intact.
"""
from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.exceptions import AirflowFailException
from airflow.operators.python import PythonOperator
from airflow.utils.trigger_rule import TriggerRule

from pipeline import steps
from quality.checks import QualityGateError

RUN_LABEL = "{{ run_id }}"  # Airflow run id = pipeline run label (shared by all tasks)


def _guarded(fn, *args):
    """Quality/source problems are not transient: fail at once instead of retrying."""
    try:
        fn(*args)
    except (QualityGateError, steps.SourceUnavailableError) as exc:
        raise AirflowFailException(str(exc)) from exc


def _finish(label: str, status: str, error: str | None = None) -> None:
    """Return nothing: Airflow would try to store a returned Path in XCom and fail."""
    steps.finish(label, status, error)


def _task(task_id: str, fn, *args, timeout_minutes: int = 10, **kwargs) -> PythonOperator:
    return PythonOperator(
        task_id=task_id,
        python_callable=_guarded,
        op_args=[fn, *args],
        execution_timeout=timedelta(minutes=timeout_minutes),
        **kwargs,
    )


with DAG(
    dag_id="atlas_pipeline",
    description="Bronze -> Silver -> Gold e-commerce pipeline with quality gates",
    schedule="@daily",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={"owner": "data-platform", "retries": 2, "retry_delay": timedelta(minutes=2)},
    tags=["atlas", "data-quality"],
    doc_md=__doc__,
) as dag:
    init_db = _task("init_db", steps.init_database, timeout_minutes=2)
    check_sources = _task("check_sources", steps.check_sources, RUN_LABEL, timeout_minutes=2)
    ingest = _task("ingest", steps.ingest, RUN_LABEL)
    validate_bronze = _task("validate_bronze", steps.validate_bronze, RUN_LABEL, timeout_minutes=5)
    silver_run = _task("dbt_silver_run", steps.dbt_step, RUN_LABEL, "silver_run", timeout_minutes=15)
    silver_test = _task("dbt_silver_test", steps.dbt_step, RUN_LABEL, "silver_test", timeout_minutes=15)
    validate_silver = _task("validate_silver", steps.validate_silver, RUN_LABEL, timeout_minutes=5)
    gold_run = _task("dbt_gold_run", steps.dbt_step, RUN_LABEL, "gold_run", timeout_minutes=15)
    gold_test = _task("dbt_gold_test", steps.dbt_step, RUN_LABEL, "gold_test", timeout_minutes=15)
    publish = _task("publish_gold", steps.publish_gold, RUN_LABEL, timeout_minutes=5)

    record_success = PythonOperator(
        task_id="record_success", python_callable=_finish, op_args=[RUN_LABEL, "success"],
        trigger_rule=TriggerRule.ALL_SUCCESS,
    )
    record_failure = PythonOperator(
        task_id="record_failure", python_callable=_finish,
        op_args=[RUN_LABEL, "failed", "see failed task logs and ops.step_runs"],
        trigger_rule=TriggerRule.ONE_FAILED,
    )

    chain = [init_db, check_sources, ingest, validate_bronze, silver_run, silver_test,
             validate_silver, gold_run, gold_test, publish, record_success]
    for upstream, downstream in zip(chain, chain[1:], strict=False):
        upstream >> downstream
    [init_db, check_sources, ingest, validate_bronze, silver_run, silver_test,
     validate_silver, gold_run, gold_test, publish] >> record_failure
