FROM apache/airflow:2.10.5-python3.12

COPY requirements.txt requirements-dbt.txt /tmp/

USER root

RUN python -m venv /opt/dbt-venv \
 && /opt/dbt-venv/bin/pip install --no-cache-dir -r /tmp/requirements-dbt.txt \
 && chown -R airflow:root /opt/dbt-venv

USER airflow

RUN pip install --no-cache-dir -r /tmp/requirements.txt

ENV PYTHONPATH=/opt/atlas \
    ATLAS_PROJECT_ROOT=/opt/atlas \
    ATLAS_DBT_BIN=/opt/dbt-venv/bin/dbt \
    AIRFLOW__CORE__DAGS_FOLDER=/opt/atlas/dags \
    AIRFLOW__CORE__LOAD_EXAMPLES=False

WORKDIR /opt/atlas