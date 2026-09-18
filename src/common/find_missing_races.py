from __future__ import annotations

import argparse
import json
import os

from dotenv import load_dotenv
from trino.dbapi import connect
from trino.exceptions import TrinoUserError

try:
    from .race_schedule import get_completed_races
except ImportError:
    from race_schedule import get_completed_races

load_dotenv()


def get_trino_connection():
    """
    Create a Trino connection using environment variables.

    Host execution defaults:
        localhost:8081

    Container execution normally overrides these with:
        TRINO_HOST=trino
        TRINO_PORT=8080
    """

    host = os.getenv("TRINO_HOST", "localhost")
    port = int(os.getenv("TRINO_PORT", "8081"))

    return connect(
        host=host,
        port=port,
        user="f1_season_discovery",
        catalog="iceberg",
        schema="bronze",
        http_scheme="http",
    )


def get_event_slugs(
    table: str,
    year: int,
    session: str,
) -> set[str]:
    """
    Return event slugs already present in a specific Iceberg table.

    During a clean/cold rebuild, an Iceberg table or schema may not
    exist yet. In that case, treat the table as containing zero races.
    """

    safe_session = session.replace("'", "''")

    connection = get_trino_connection()
    cursor = connection.cursor()

    query = f"""
        SELECT DISTINCT event_slug
        FROM {table}
        WHERE season = {int(year)}
          AND session_type = '{safe_session}'
          AND event_slug IS NOT NULL
        ORDER BY event_slug
    """

    try:

        cursor.execute(query)

        loaded = {
            row[0]
            for row in cursor.fetchall()
            if row[0] is not None
        }

        return loaded

    except TrinoUserError as exc:

        error_name = getattr(
            exc,
            "error_name",
            None,
        )

        # Expected during a cold-start rebuild.
        if error_name in {
            "TABLE_NOT_FOUND",
            "SCHEMA_NOT_FOUND",
        }:
            return set()

        raise

    finally:

        cursor.close()
        connection.close()

def get_event_drivers(
    table: str,
    year: int,
    session: str,
) -> dict[str, set[str]]:
    """
    Return the distinct telemetry/lap drivers present for
    each event slug in a specific Iceberg table.

    Missing tables or schemas are treated as an empty state
    so season discovery can operate during a cold start.
    """

    host = os.getenv(
        "TRINO_HOST",
        "localhost",
    )

    port = int(
        os.getenv(
            "TRINO_PORT",
            "8081",
        )
    )

    safe_session = (
        session.replace(
            "'",
            "''",
        )
    )

    connection = connect(
        host=host,
        port=port,
        user="f1_season_discovery",
        catalog="iceberg",
        schema="bronze",
        http_scheme="http",
    )

    cursor = (
        connection.cursor()
    )

    query = f"""
        SELECT DISTINCT
            event_slug,
            driver_code
        FROM {table}
        WHERE season = {int(year)}
          AND session_type = '{safe_session}'
          AND event_slug IS NOT NULL
          AND driver_code IS NOT NULL
        ORDER BY
            event_slug,
            driver_code
    """

    try:

        cursor.execute(
            query
        )

        rows = (
            cursor.fetchall()
        )

    except TrinoUserError as exc:

        error_name = getattr(
            exc,
            "error_name",
            "",
        )

        if error_name in {
            "TABLE_NOT_FOUND",
            "SCHEMA_NOT_FOUND",
        }:

            return {}

        raise

    finally:

        try:
            cursor.close()
        except Exception:
            pass

        try:
            connection.close()
        except Exception:
            pass

    drivers_by_event: dict[
        str,
        set[str],
    ] = {}

    for (
        event_slug,
        driver_code,
    ) in rows:

        # Defensive protection in addition to the SQL filter.
        # This also protects the function if a future query
        # changes and NULL values somehow reach this point.
        if (
            event_slug is None
            or driver_code is None
        ):
            continue

        drivers_by_event.setdefault(
            str(event_slug),
            set(),
        ).add(
            str(driver_code)
        )

    return drivers_by_event


def find_incomplete_races(
    year: int,
    session: str = "R",
) -> list[dict]:

    completed = get_completed_races(year)

    # --------------------------------------------------------
    # Bronze session-level datasets
    # --------------------------------------------------------

    bronze_laps = get_event_slugs(
        "iceberg.bronze.laps",
        year,
        session,
    )

    bronze_results = get_event_slugs(
        "iceberg.bronze.results",
        year,
        session,
    )

    bronze_weather = get_event_slugs(
        "iceberg.bronze.weather",
        year,
        session,
    )

    # --------------------------------------------------------
    # Driver-level completeness
    #
    # Bronze laps defines the expected driver population.
    # Telemetry must contain exactly the same driver set.
    # --------------------------------------------------------

    expected_drivers = get_event_drivers(
        "iceberg.bronze.laps",
        year,
        session,
    )

    bronze_telemetry_drivers = get_event_drivers(
        "iceberg.bronze.telemetry",
        year,
        session,
    )

    silver_telemetry_drivers = get_event_drivers(
        "iceberg.silver.silver_telemetry",
        year,
        session,
    )

    incomplete: list[dict] = []

    for race in completed:

        slug = race["event_slug"]

        # ----------------------------------------------------
        # Bronze session datasets
        # ----------------------------------------------------

        needs_laps = (
            slug not in bronze_laps
        )

        needs_results = (
            slug not in bronze_results
        )

        needs_weather = (
            slug not in bronze_weather
        )

        needs_session_ingestion = any(
            [
                needs_laps,
                needs_results,
                needs_weather,
            ]
        )

        # ----------------------------------------------------
        # Expected driver population
        # ----------------------------------------------------

        race_expected_drivers = (
            expected_drivers.get(
                slug,
                set(),
            )
        )

        race_bronze_drivers = (
            bronze_telemetry_drivers.get(
                slug,
                set(),
            )
        )

        race_silver_drivers = (
            silver_telemetry_drivers.get(
                slug,
                set(),
            )
        )

        # ----------------------------------------------------
        # Bronze telemetry completeness
        #
        # Bronze telemetry is incomplete when:
        #
        # 1. Bronze laps itself still needs rebuilding
        # 2. There is no expected driver population
        # 3. Telemetry driver set does not match lap drivers
        #
        # Example:
        #
        # laps      = 22 drivers
        # telemetry = 21 drivers
        #
        # => needs_bronze_telemetry = True
        # ----------------------------------------------------

        needs_bronze_telemetry = (
            needs_laps
            or not race_expected_drivers
            or race_bronze_drivers
            != race_expected_drivers
        )

        # ----------------------------------------------------
        # Silver telemetry completeness
        #
        # Silver cannot be complete if Bronze is incomplete.
        #
        # Otherwise Silver must contain exactly the same
        # driver population as Bronze laps.
        # ----------------------------------------------------

        needs_silver_telemetry = (
            needs_bronze_telemetry
            or not race_expected_drivers
            or race_silver_drivers
            != race_expected_drivers
        )

        # ----------------------------------------------------
        # Determine whether race requires any work
        # ----------------------------------------------------

        fully_complete = not any(
            [
                needs_session_ingestion,
                needs_bronze_telemetry,
                needs_silver_telemetry,
            ]
        )

        if fully_complete:
            continue

        race = dict(race)

        race.update(
            {
                "needs_session_ingestion":
                    needs_session_ingestion,

                "needs_laps":
                    needs_laps,

                "needs_results":
                    needs_results,

                "needs_weather":
                    needs_weather,

                "needs_bronze_telemetry":
                    needs_bronze_telemetry,

                "needs_silver_telemetry":
                    needs_silver_telemetry,
            }
        )

        incomplete.append(race)

    return incomplete


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Find completed F1 races that are not fully "
            "processed through the lakehouse."
        )
    )

    parser.add_argument(
        "--year",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--session",
        default="R",
    )

    parser.add_argument(
        "--json",
        action="store_true",
    )

    args = parser.parse_args()

    completed = get_completed_races(
        args.year
    )

    incomplete = find_incomplete_races(
        year=args.year,
        session=args.session,
    )

    # --------------------------------------------------------
    # Machine-readable Airflow output
    # --------------------------------------------------------

    if args.json:

        print(
            json.dumps(
                incomplete
            )
        )

        return

    # --------------------------------------------------------
    # Human-readable output
    # --------------------------------------------------------

    print()
    print("=" * 78)

    print(
        f"F1 LAKEHOUSE COMPLETENESS CHECK — "
        f"{args.year}"
    )

    print("=" * 78)

    print()

    print(
        f"Completed races : "
        f"{len(completed)}"
    )

    print(
        f"Incomplete      : "
        f"{len(incomplete)}"
    )

    print(
        f"Fully processed : "
        f"{len(completed) - len(incomplete)}"
    )

    print()

    print(
        "Incomplete races"
    )

    print("-" * 78)

    if not incomplete:

        print(
            "✓ Lakehouse is fully up to date."
        )

    else:

        for race in incomplete:

            missing = []

            if race[
                "needs_laps"
            ]:
                missing.append(
                    "bronze.laps"
                )

            if race[
                "needs_results"
            ]:
                missing.append(
                    "bronze.results"
                )

            if race[
                "needs_weather"
            ]:
                missing.append(
                    "bronze.weather"
                )

            if race[
                "needs_bronze_telemetry"
            ]:
                missing.append(
                    "bronze.telemetry"
                )

            if race[
                "needs_silver_telemetry"
            ]:
                missing.append(
                    "silver.telemetry"
                )

            print(
                f"Round "
                f"{race['round']:>2}: "
                f"{race['event']:<30} "
                f"missing: "
                f"{', '.join(missing)}"
            )

    print()


if __name__ == "__main__":
    main()
