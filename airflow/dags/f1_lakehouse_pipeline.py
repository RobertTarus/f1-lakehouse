from __future__ import annotations

import subprocess

from datetime import timedelta

import pendulum

from airflow.sdk import (
    Param,
    dag,
    get_current_context,
    task,
)


PROJECT = "/opt/airflow/project"

PIPELINE_PY = (
    "/opt/airflow/venvs/"
    "pipeline/bin/python"
)

DBT = (
    "/opt/airflow/venvs/"
    "dbt/bin/dbt"
)


@dag(
    dag_id="f1_lakehouse_pipeline",

    description=(
        "FastF1 → SeaweedFS → Iceberg "
        "→ Trino → dbt"
    ),

    schedule=None,

    start_date=pendulum.datetime(
        2026,
        1,
        1,
        tz="UTC",
    ),

    catchup=False,

    max_active_runs=1,

    default_args={
        "retries": 1,
        "retry_delay": timedelta(
            minutes=2
        ),
    },

    params={
        "year": Param(
            2026,
            type="integer",
            minimum=2018,
            title="Season",
        ),

        "event": Param(
            "Italian Grand Prix",
            type="string",
            title="Grand Prix",
        ),

        "session": Param(
            "R",
            enum=[
                "R",
                "Q",
                "S",
                "SQ",
                "FP1",
                "FP2",
                "FP3",
            ],
            title="Session",
        ),
    },

    tags=[
        "f1",
        "lakehouse",
        "iceberg",
        "dbt",
    ],
)
def f1_lakehouse_pipeline():

    @task
    def run_step(step: str):

        context = get_current_context()

        params = context["params"]

        year = str(params["year"])
        event = str(params["event"])
        session = str(params["session"])

        common = [
            "--year",
            year,
            "--event",
            event,
            "--session",
            session,
        ]

        commands = {

            "ingest_session": [
                PIPELINE_PY,
                "src/ingestion/ingest_session.py",
                *common,
            ],

            "promote_laps": [
                PIPELINE_PY,
                "src/iceberg/promote_laps.py",
                *common,
            ],

            "promote_results": [
                PIPELINE_PY,
                "src/iceberg/promote_bronze.py",
                "--dataset",
                "results",
                *common,
            ],

            "promote_weather": [
                PIPELINE_PY,
                "src/iceberg/promote_bronze.py",
                "--dataset",
                "weather",
                *common,
            ],

            "ingest_telemetry": [
                PIPELINE_PY,
                "src/ingestion/ingest_telemetry.py",
                *common,
            ],

            "promote_telemetry": [
                PIPELINE_PY,
                "src/iceberg/promote_all_telemetry.py",
                *common,
            ],

            "dbt_source_tests": [
                DBT,
                "test",
                "--select",
                "source:bronze",
                "--project-dir",
                "dbt",
                "--profiles-dir",
                "configs/dbt",
            ],

            "dbt_build": [
                DBT,
                "build",
                "--select",
                "+race_driver_performance",
                "+lap_telemetry_metrics",
                "--project-dir",
                "dbt",
                "--profiles-dir",
                "configs/dbt",
            ],

            "validate_gold": [
                PIPELINE_PY,
                "src/validation/validate_gold.py",
            ],
        }

        command = commands[step]

        print(
            "Executing:",
            " ".join(command),
        )

        subprocess.run(
            command,
            cwd=PROJECT,
            check=True,
        )

    ingest_session = run_step.override(
        task_id="ingest_session"
    )("ingest_session")

    promote_laps = run_step.override(
        task_id="promote_laps"
    )("promote_laps")

    promote_results = run_step.override(
        task_id="promote_results"
    )("promote_results")

    promote_weather = run_step.override(
        task_id="promote_weather"
    )("promote_weather")

    ingest_telemetry = run_step.override(
        task_id="ingest_telemetry"
    )("ingest_telemetry")

    promote_telemetry = run_step.override(
        task_id="promote_telemetry"
    )("promote_telemetry")

    dbt_source_tests = run_step.override(
        task_id="dbt_source_tests"
    )("dbt_source_tests")

    dbt_build = run_step.override(
        task_id="dbt_build"
    )("dbt_build")

    validate_gold = run_step.override(
        task_id="validate_gold"
    )("validate_gold")


    ingest_session >> [
        promote_laps,
        promote_results,
        promote_weather,
        ingest_telemetry,
    ]

    ingest_telemetry >> promote_telemetry

    [
        promote_laps,
        promote_results,
        promote_weather,
        promote_telemetry,
    ] >> dbt_source_tests

    dbt_source_tests >> dbt_build

    dbt_build >> validate_gold


f1_lakehouse_pipeline()
