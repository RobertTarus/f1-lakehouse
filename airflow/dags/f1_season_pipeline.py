from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

from airflow.sdk import (
    Param,
    dag,
    get_current_context,
    task,
    task_group,
)


PROJECT = "/opt/airflow/project"

PIPELINE_PY = "/opt/airflow/venvs/pipeline/bin/python"
DBT = "/opt/airflow/venvs/dbt/bin/dbt"


def run_command(
    command: list[str],
) -> None:
    """
    Run a command from the project root.

    A non-zero exit status causes the Airflow task
    to fail immediately.
    """

    print()
    print("=" * 80)
    print("RUNNING COMMAND")
    print("=" * 80)

    print(
        " ".join(
            command
        )
    )

    print("=" * 80)
    print()

    subprocess.run(
        command,
        cwd=PROJECT,
        check=True,
    )


def race_args(
    race: dict,
) -> list[str]:
    """
    Common CLI arguments used by ingestion
    and Bronze promotion scripts.
    """

    return [
        "--year",
        str(
            race["year"]
        ),
        "--event",
        race["event"],
        "--session",
        race["session"],
    ]


@dag(
    dag_id="f1_season_pipeline",
    description=(
        "Discover incomplete Formula 1 races, "
        "process missing stages, validate telemetry, "
        "and build analytics models."
    ),
    schedule=None,
    start_date=datetime(
        2026,
        1,
        1,
        tzinfo=timezone.utc,
    ),
    catchup=False,
    max_active_runs=1,
    params={
        "year": Param(
            2026,
            type="integer",
            title="Season",
        ),
        "session": Param(
            "R",
            type="string",
            title="Session",
        ),
        "start_round": Param(
            1,
            type="integer",
            minimum=1,
            title="Start Round",
        ),
        "end_round": Param(
            99,
            type="integer",
            minimum=1,
            title="End Round",
        ),
    },
    tags=[
        "f1",
        "lakehouse",
        "season",
        "backfill",
        "quality",
    ],
)
def f1_season_pipeline():

    # ========================================================
    # DISCOVERY
    # ========================================================

    @task
    def discover_missing_races() -> list[dict]:

        context = (
            get_current_context()
        )

        params = (
            context["params"]
        )

        year = int(
            params["year"]
        )

        session = str(
            params["session"]
        )

        start_round = int(
            params["start_round"]
        )

        end_round = int(
            params["end_round"]
        )

        command = [
            PIPELINE_PY,
            "src/common/"
            "find_missing_races.py",
            "--year",
            str(year),
            "--session",
            session,
            "--json",
        ]

        result = subprocess.run(
            command,
            cwd=PROJECT,
            check=True,
            capture_output=True,
            text=True,
        )

        lines = [
            line.strip()
            for line
            in result.stdout.splitlines()
            if line.strip()
        ]

        if not lines:

            raise RuntimeError(
                "Race discovery "
                "returned no output."
            )

        races = json.loads(
            lines[-1]
        )

        races = [
            race
            for race in races
            if start_round
            <= int(
                race["round"]
            )
            <= end_round
        ]

        print()
        print("=" * 80)

        print(
            "RACES SELECTED FOR PROCESSING"
        )

        print("=" * 80)

        print(
            f"Season      : "
            f"{year}"
        )

        print(
            f"Session     : "
            f"{session}"
        )

        print(
            f"Round range : "
            f"{start_round} - "
            f"{end_round}"
        )

        print(
            f"Selected    : "
            f"{len(races)}"
        )

        print()

        if not races:

            print(
                "Lakehouse is already "
                "complete for the selected "
                "round range."
            )

        for race in races:

            missing = []

            if race.get(
                "needs_laps",
                False,
            ):

                missing.append(
                    "bronze.laps"
                )

            if race.get(
                "needs_results",
                False,
            ):

                missing.append(
                    "bronze.results"
                )

            if race.get(
                "needs_weather",
                False,
            ):

                missing.append(
                    "bronze.weather"
                )

            if race.get(
                "needs_bronze_telemetry",
                False,
            ):

                missing.append(
                    "bronze.telemetry"
                )

            if race.get(
                "needs_silver_telemetry",
                False,
            ):

                missing.append(
                    "silver.telemetry"
                )

            print(
                f"Round "
                f"{race['round']:>2}: "
                f"{race['event']}"
            )

            print(
                "    Missing: "
                + ", ".join(
                    missing
                )
            )

        return races

    # ========================================================
    # PER-RACE PROCESSING
    # ========================================================

    @task_group(
        group_id="process_race"
    )
    def process_race(
        race,
    ):

        # ====================================================
        # RAW SESSION
        # ====================================================

        @task
        def ingest_session(
            race: dict,
        ) -> None:

            if not race.get(
                "needs_session_ingestion",
                False,
            ):

                print(
                    f"{race['event']}: "
                    f"session ingestion "
                    f"already complete."
                )

                return

            run_command(
                [
                    PIPELINE_PY,
                    "src/ingestion/"
                    "ingest_session.py",
                    *race_args(
                        race
                    ),
                ]
            )

        # ====================================================
        # BRONZE LAPS
        # ====================================================

        @task(
            max_active_tis_per_dag=1
        )
        def promote_laps(
            race: dict,
        ) -> None:

            if not race.get(
                "needs_laps",
                False,
            ):

                print(
                    f"{race['event']}: "
                    f"bronze.laps "
                    f"already exists."
                )

                return

            run_command(
                [
                    PIPELINE_PY,
                    "src/iceberg/"
                    "promote_laps.py",
                    *race_args(
                        race
                    ),
                ]
            )

        # ====================================================
        # BRONZE RESULTS
        # ====================================================

        @task(
            max_active_tis_per_dag=1
        )
        def promote_results(
            race: dict,
        ) -> None:

            if not race.get(
                "needs_results",
                False,
            ):

                print(
                    f"{race['event']}: "
                    f"bronze.results "
                    f"already exists."
                )

                return

            run_command(
                [
                    PIPELINE_PY,
                    "src/iceberg/"
                    "promote_bronze.py",
                    "--dataset",
                    "results",
                    *race_args(
                        race
                    ),
                ]
            )

        # ====================================================
        # BRONZE WEATHER
        # ====================================================

        @task(
            max_active_tis_per_dag=1
        )
        def promote_weather(
            race: dict,
        ) -> None:

            if not race.get(
                "needs_weather",
                False,
            ):

                print(
                    f"{race['event']}: "
                    f"bronze.weather "
                    f"already exists."
                )

                return

            run_command(
                [
                    PIPELINE_PY,
                    "src/iceberg/"
                    "promote_bronze.py",
                    "--dataset",
                    "weather",
                    *race_args(
                        race
                    ),
                ]
            )

        # ====================================================
        # RAW TELEMETRY
        # ====================================================

        @task
        def ingest_telemetry(
            race: dict,
        ) -> None:

            if not race.get(
                "needs_bronze_telemetry",
                False,
            ):

                print(
                    f"{race['event']}: "
                    f"Bronze telemetry "
                    f"already exists. "
                    f"Raw telemetry "
                    f"ingestion skipped."
                )

                return

            run_command(
                [
                    PIPELINE_PY,
                    "src/ingestion/"
                    "ingest_telemetry.py",
                    *race_args(
                        race
                    ),
                ]
            )

        # ====================================================
        # BRONZE TELEMETRY
        #
        # Only one mapped Bronze telemetry promotion may run
        # at a time because every race writes to the same
        # Iceberg bronze.telemetry table.
        #
        # This prevents concurrent Iceberg commits from
        # conflicting with one another.
        # ====================================================

        @task(
            max_active_tis_per_dag=1
        )
        def promote_telemetry(
            race: dict,
        ) -> None:

            if not race.get(
                "needs_bronze_telemetry",
                False,
            ):

                print(
                    f"{race['event']}: "
                    f"bronze.telemetry "
                    f"already exists."
                )

                return

            run_command(
                [
                    PIPELINE_PY,
                    "src/iceberg/"
                    "promote_all_telemetry.py",
                    *race_args(
                        race
                    ),
                ]
            )

        # ====================================================
        # SILVER TELEMETRY
        #
        # Only one mapped Silver telemetry transformation
        # may run at a time to protect Trino memory.
        # ====================================================

        @task(
            max_active_tis_per_dag=1
        )
        def load_silver_telemetry(
            race: dict,
        ) -> None:

            if not race.get(
                "needs_silver_telemetry",
                False,
            ):

                print(
                    f"{race['event']}: "
                    f"silver telemetry "
                    f"already exists."
                )

                return

            print()
            print("=" * 80)

            print(
                "LOADING SILVER TELEMETRY"
            )

            print("=" * 80)

            print(
                f"Season : "
                f"{race['year']}"
            )

            print(
                f"Race   : "
                f"{race['event']}"
            )

            print(
                f"Slug   : "
                f"{race['event_slug']}"
            )

            print(
                f"Session: "
                f"{race['session']}"
            )

            print("=" * 80)
            print()

            run_command(
                [
                    PIPELINE_PY,
                    "src/iceberg/"
                    "load_silver_telemetry.py",
                    "--year",
                    str(
                        race["year"]
                    ),
                    "--event-slug",
                    race[
                        "event_slug"
                    ],
                    "--session",
                    race[
                        "session"
                    ],
                ]
            )

        # ====================================================
        # CREATE TASKS
        # ====================================================

        session_ingested = (
            ingest_session(
                race
            )
        )

        laps = (
            promote_laps(
                race
            )
        )

        results = (
            promote_results(
                race
            )
        )

        weather = (
            promote_weather(
                race
            )
        )

        telemetry_raw = (
            ingest_telemetry(
                race
            )
        )

        telemetry_bronze = (
            promote_telemetry(
                race
            )
        )

        telemetry_silver = (
            load_silver_telemetry(
                race
            )
        )

        # ====================================================
        # PER-RACE DEPENDENCIES
        # ====================================================

        session_ingested >> [
            laps,
            results,
            weather,
            telemetry_raw,
        ]

        telemetry_raw >> (
            telemetry_bronze
        )

        telemetry_bronze >> (
            telemetry_silver
        )

    # ========================================================
    # TELEMETRY QUALITY GATE
    # ========================================================

    @task(
        trigger_rule="none_failed"
    )
    def telemetry_quality_gate() -> None:

        context = (
            get_current_context()
        )

        params = (
            context["params"]
        )

        year = int(
            params["year"]
        )

        session = str(
            params["session"]
        )

        print()
        print("=" * 80)

        print(
            "RUNNING TELEMETRY QUALITY GATE"
        )

        print("=" * 80)
        print()

        run_command(
            [
                PIPELINE_PY,
                "src/validation/"
                "validate_telemetry_quality.py",
                "--year",
                str(year),
                "--session",
                session,
            ]
        )

    # ========================================================
    # DBT SOURCE TESTS
    # ========================================================

    @task(
        trigger_rule="none_failed"
    )
    def dbt_source_tests() -> None:

        print()
        print("=" * 80)

        print(
            "RUNNING DBT BRONZE SOURCE TESTS"
        )

        print("=" * 80)
        print()

        run_command(
            [
                DBT,
                "test",
                "--select",
                "source:bronze",
                "--project-dir",
                "dbt",
                "--profiles-dir",
                "configs/dbt",
                "--threads",
                "2",
            ]
        )

    # ========================================================
    # DBT SILVER + GOLD
    # ========================================================

    @task
    def dbt_build() -> None:

        print()
        print("=" * 80)

        print(
            "RUNNING DBT SILVER + GOLD BUILD"
        )

        print("=" * 80)
        print()

        run_command(
            [
                DBT,
                "build",

                "--select",
                "silver_laps",
                "silver_results",
                "silver_weather",
                "race_driver_performance",
                "lap_telemetry_metrics",

                "--exclude",
                "tag:externally_loaded",

                "--project-dir",
                "dbt",

                "--profiles-dir",
                "configs/dbt",

                "--threads",
                "2",
            ]
        )

    # ========================================================
    # GOLD VALIDATION
    # ========================================================

    @task
    def validate_gold() -> None:

        print()
        print("=" * 80)

        print(
            "VALIDATING GOLD LAYER"
        )

        print("=" * 80)
        print()

        run_command(
            [
                PIPELINE_PY,
                "src/validation/"
                "validate_gold.py",
            ]
        )

    # ========================================================
    # DAG GRAPH
    # ========================================================

    incomplete_races = (
        discover_missing_races()
    )

    race_processing = (
        process_race.expand(
            race=incomplete_races
        )
    )

    quality_gate = (
        telemetry_quality_gate()
    )

    source_tests = (
        dbt_source_tests()
    )

    build = (
        dbt_build()
    )

    validation = (
        validate_gold()
    )

    race_processing >> (
        quality_gate
    )

    quality_gate >> (
        source_tests
    )

    source_tests >> (
        build
    )

    build >> (
        validation
    )


dag = f1_season_pipeline()
