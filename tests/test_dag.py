"""DAG structure tests. Skipped when Apache Airflow is not installed (it is not a project dependency)."""
from pathlib import Path

import pytest

pytest.importorskip("airflow")

from airflow.models import DagBag  # noqa: E402

DAGS = Path(__file__).parent.parent / "dags"


@pytest.fixture(scope="module")
def dag():
    bag = DagBag(dag_folder=str(DAGS), include_examples=False)
    assert not bag.import_errors, bag.import_errors
    return bag.get_dag("atlas_pipeline")


def test_expected_task_order(dag):
    order = ["init_db", "check_sources", "ingest", "validate_bronze", "dbt_silver_run", "dbt_silver_test",
             "validate_silver", "dbt_gold_run", "dbt_gold_test", "publish_gold", "record_success"]
    for upstream, downstream in zip(order, order[1:], strict=False):
        assert downstream in dag.get_task(upstream).downstream_task_ids


def test_publish_only_after_tests_and_gates(dag):
    upstream = dag.get_task("publish_gold").upstream_task_ids
    assert upstream == {"dbt_gold_test"}


def test_retries_timeouts_and_single_active_run(dag):
    assert dag.max_active_runs == 1 and dag.catchup is False
    for task in dag.tasks:
        if task.task_id.startswith("record_"):
            continue
        assert task.retries == 2 and task.execution_timeout is not None


def test_failure_recorder_runs_on_any_failure(dag):
    assert dag.get_task("record_failure").trigger_rule == "one_failed"
