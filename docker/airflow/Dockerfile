FROM apache/airflow:3.3.1-python3.12


# ---------------------------------------------------------
# Pipeline environment
# FastF1 / SeaweedFS / PyIceberg
# ---------------------------------------------------------

COPY docker/airflow/requirements-pipeline.txt /tmp/requirements-pipeline.txt

RUN python -m venv /opt/airflow/venvs/pipeline \
    && /opt/airflow/venvs/pipeline/bin/pip install --upgrade pip \
    && /opt/airflow/venvs/pipeline/bin/pip install \
       --no-cache-dir \
       -r /tmp/requirements-pipeline.txt


# ---------------------------------------------------------
# dbt environment
# ---------------------------------------------------------

COPY docker/airflow/requirements-dbt.txt /tmp/requirements-dbt.txt

RUN python -m venv /opt/airflow/venvs/dbt \
    && /opt/airflow/venvs/dbt/bin/pip install --upgrade pip \
    && /opt/airflow/venvs/dbt/bin/pip install \
       --no-cache-dir \
       -r /tmp/requirements-dbt.txt
