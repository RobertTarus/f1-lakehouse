from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict

from trino.dbapi import connect


# ============================================================
# QUALITY THRESHOLDS
# ============================================================

DEFAULT_MIN_ROWS = 100_000
DEFAULT_MIN_DRIVERS = 15
DEFAULT_MIN_LAPS = 10
DEFAULT_MIN_DRIVER_ROWS = 100


# ============================================================
# TRINO CONNECTION
# ============================================================

def get_connection():
    """
    Connect to Trino.

    Local environment:
        localhost:8081

    Airflow:
        trino:8080
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

    return connect(
        host=host,
        port=port,
        user="telemetry_quality_gate",
        catalog="iceberg",
        schema="silver",
        http_scheme="http",
    )


# ============================================================
# SCHEMA HELPERS
# ============================================================

def get_table_columns(
    cursor,
    schema_name: str,
    table_name: str,
) -> set[str]:
    """
    Return lowercase column names for an Iceberg table.
    """

    query = f"""
        SELECT column_name

        FROM iceberg.information_schema.columns

        WHERE table_schema = '{schema_name}'
          AND table_name = '{table_name}'
    """

    cursor.execute(query)

    return {
        str(row[0]).lower()
        for row in cursor.fetchall()
    }


def find_column(
    columns: set[str],
    candidates: list[str],
    description: str,
) -> str:
    """
    Find the first matching column name.
    """

    for candidate in candidates:

        candidate = candidate.lower()

        if candidate in columns:
            return candidate

    raise RuntimeError(
        f"Could not identify {description}. "
        f"Available columns: "
        f"{sorted(columns)}"
    )


# ============================================================
# SILVER RACE METRICS
# ============================================================

def get_race_metrics(
    cursor,
    year: int,
    session: str,
):
    """
    Calculate race-level Silver telemetry quality metrics.
    """

    safe_session = (
        session
        .replace("'", "''")
    )

    query = f"""
        SELECT
            event_slug,

            COUNT(*) AS telemetry_rows,

            COUNT(
                DISTINCT driver_code
            ) AS drivers,

            COUNT(
                DISTINCT lap_number
            ) AS laps,

            SUM(
                CASE
                    WHEN driver_code IS NULL
                         OR TRIM(driver_code) = ''
                    THEN 1
                    ELSE 0
                END
            ) AS invalid_driver_rows,

            SUM(
                CASE
                    WHEN lap_number IS NULL
                    THEN 1
                    ELSE 0
                END
            ) AS invalid_lap_rows,

            SUM(
                CASE
                    WHEN sample_time_ms IS NULL
                    THEN 1
                    ELSE 0
                END
            ) AS invalid_sample_time_rows,

            SUM(
                CASE
                    WHEN speed_kph IS NOT NULL
                         AND (
                             speed_kph < 0
                             OR speed_kph > 400
                         )
                    THEN 1
                    ELSE 0
                END
            ) AS invalid_speed_rows,

            SUM(
                CASE
                    WHEN throttle_pct IS NOT NULL
                         AND (
                             throttle_pct < 0
                             OR throttle_pct > 100
                         )
                    THEN 1
                    ELSE 0
                END
            ) AS invalid_throttle_rows,

            SUM(
                CASE
                    WHEN rpm IS NOT NULL
                         AND (
                             rpm < 0
                             OR rpm > 20000
                         )
                    THEN 1
                    ELSE 0
                END
            ) AS invalid_rpm_rows,

            SUM(
                CASE
                    WHEN gear IS NOT NULL
                         AND (
                             gear < 0
                             OR gear > 8
                         )
                    THEN 1
                    ELSE 0
                END
            ) AS invalid_gear_rows

        FROM iceberg.silver.silver_telemetry

        WHERE season = {int(year)}
          AND session_type = '{safe_session}'

        GROUP BY event_slug

        ORDER BY event_slug
    """

    cursor.execute(query)

    return cursor.fetchall()


# ============================================================
# SILVER DRIVER VOLUME
# ============================================================

def get_driver_metrics(
    cursor,
    year: int,
    session: str,
):
    """
    Return Silver telemetry row count for every
    race / driver pair.
    """

    safe_session = (
        session
        .replace("'", "''")
    )

    query = f"""
        SELECT
            event_slug,
            driver_code,
            COUNT(*) AS telemetry_rows

        FROM iceberg.silver.silver_telemetry

        WHERE season = {int(year)}
          AND session_type = '{safe_session}'

        GROUP BY
            event_slug,
            driver_code

        ORDER BY
            event_slug,
            driver_code
    """

    cursor.execute(query)

    return cursor.fetchall()


# ============================================================
# RESULTS ROSTER
# ============================================================

def get_results_drivers(
    cursor,
    year: int,
    session: str,
) -> dict[str, set[str]]:
    """
    Return the official race roster from bronze.results.

    This is informational because a driver may appear in
    results but have no usable race laps, for example a DNS.
    """

    safe_session = (
        session
        .replace("'", "''")
    )

    columns = get_table_columns(
        cursor,
        "bronze",
        "results",
    )

    driver_column = find_column(
        columns,
        [
            "driver_code",
            "abbreviation",
            "driver",
        ],
        "driver column in bronze.results",
    )

    query = f"""
        SELECT DISTINCT
            event_slug,

            UPPER(
                TRIM(
                    CAST(
                        {driver_column}
                        AS VARCHAR
                    )
                )
            ) AS driver_code

        FROM iceberg.bronze.results

        WHERE season = {int(year)}
          AND session_type = '{safe_session}'
          AND {driver_column} IS NOT NULL
    """

    cursor.execute(query)

    drivers = defaultdict(set)

    for (
        event_slug,
        driver_code,
    ) in cursor.fetchall():

        if event_slug is None:
            continue

        if driver_code is None:
            continue

        driver_code = (
            str(driver_code)
            .strip()
            .upper()
        )

        if not driver_code:
            continue

        drivers[
            str(event_slug)
        ].add(
            driver_code
        )

    return dict(drivers)


# ============================================================
# EXPECTED TELEMETRY DRIVERS
# ============================================================

def get_expected_drivers_from_laps(
    cursor,
    year: int,
    session: str,
) -> dict[str, set[str]]:
    """
    Determine which drivers should have telemetry.

    bronze.laps is used instead of bronze.results because
    the normalized results table does not contain the
    FastF1 'Laps' field.

    If a driver has at least one lap in bronze.laps, that
    driver is expected to appear in Silver telemetry.
    """

    safe_session = (
        session
        .replace("'", "''")
    )

    columns = get_table_columns(
        cursor,
        "bronze",
        "laps",
    )

    driver_column = find_column(
        columns,
        [
            "driver_code",
            "driver",
            "abbreviation",
        ],
        "driver column in bronze.laps",
    )

    lap_column = find_column(
        columns,
        [
            "lap_number",
            "lapnumber",
            "lap",
        ],
        "lap number column in bronze.laps",
    )

    print()
    print(
        f"Bronze laps driver column : "
        f"{driver_column}"
    )

    print(
        f"Bronze laps lap column    : "
        f"{lap_column}"
    )

    query = f"""
        SELECT DISTINCT
            event_slug,

            UPPER(
                TRIM(
                    CAST(
                        {driver_column}
                        AS VARCHAR
                    )
                )
            ) AS driver_code

        FROM iceberg.bronze.laps

        WHERE season = {int(year)}
          AND session_type = '{safe_session}'
          AND {driver_column} IS NOT NULL
          AND {lap_column} IS NOT NULL
    """

    cursor.execute(query)

    expected = defaultdict(set)

    for (
        event_slug,
        driver_code,
    ) in cursor.fetchall():

        if event_slug is None:
            continue

        if driver_code is None:
            continue

        driver_code = (
            str(driver_code)
            .strip()
            .upper()
        )

        if not driver_code:
            continue

        expected[
            str(event_slug)
        ].add(
            driver_code
        )

    return dict(expected)


# ============================================================
# ACTUAL SILVER TELEMETRY DRIVERS
# ============================================================

def get_actual_telemetry_drivers(
    cursor,
    year: int,
    session: str,
) -> dict[str, set[str]]:
    """
    Return drivers actually represented in Silver telemetry.
    """

    safe_session = (
        session
        .replace("'", "''")
    )

    query = f"""
        SELECT DISTINCT
            event_slug,

            UPPER(
                TRIM(driver_code)
            ) AS driver_code

        FROM iceberg.silver.silver_telemetry

        WHERE season = {int(year)}
          AND session_type = '{safe_session}'
          AND driver_code IS NOT NULL
          AND TRIM(driver_code) <> ''
    """

    cursor.execute(query)

    actual = defaultdict(set)

    for (
        event_slug,
        driver_code,
    ) in cursor.fetchall():

        if event_slug is None:
            continue

        if driver_code is None:
            continue

        actual[
            str(event_slug)
        ].add(
            str(driver_code)
            .strip()
            .upper()
        )

    return dict(actual)


# ============================================================
# VALIDATION
# ============================================================

def validate_quality(
    year: int,
    session: str,
    min_rows: int,
    min_drivers: int,
    min_laps: int,
    min_driver_rows: int,
) -> None:
    """
    Run all Silver telemetry quality checks.
    """

    connection = get_connection()
    cursor = connection.cursor()

    try:

        race_metrics = get_race_metrics(
            cursor,
            year,
            session,
        )

        driver_metrics = get_driver_metrics(
            cursor,
            year,
            session,
        )

        results_drivers = get_results_drivers(
            cursor,
            year,
            session,
        )

        expected_drivers = (
            get_expected_drivers_from_laps(
                cursor,
                year,
                session,
            )
        )

        actual_drivers = (
            get_actual_telemetry_drivers(
                cursor,
                year,
                session,
            )
        )

    finally:

        cursor.close()
        connection.close()

    if not race_metrics:

        raise RuntimeError(
            f"No Silver telemetry found for "
            f"season={year}, "
            f"session={session}"
        )

    failures = []
    warnings = []

    # ========================================================
    # HEADER
    # ========================================================

    print()
    print("=" * 110)
    print(
        "F1 SILVER TELEMETRY QUALITY GATE"
    )
    print("=" * 110)

    print(
        f"Season              : {year}"
    )

    print(
        f"Session             : {session}"
    )

    print(
        f"Minimum race rows   : "
        f"{min_rows:,}"
    )

    print(
        f"Minimum drivers     : "
        f"{min_drivers}"
    )

    print(
        f"Minimum laps        : "
        f"{min_laps}"
    )

    print(
        f"Minimum driver rows : "
        f"{min_driver_rows:,}"
    )

    # ========================================================
    # RACE-LEVEL QUALITY
    # ========================================================

    print()
    print("=" * 110)
    print(
        "RACE-LEVEL TELEMETRY QUALITY"
    )
    print("=" * 110)

    print(
        f"{'EVENT':<32}"
        f"{'ROWS':>14}"
        f"{'DRIVERS':>10}"
        f"{'LAPS':>8}"
        f"{'STATUS':>12}"
    )

    print("-" * 110)

    silver_events = set()

    for row in race_metrics:

        (
            event_slug,
            telemetry_rows,
            drivers,
            laps,
            invalid_driver_rows,
            invalid_lap_rows,
            invalid_sample_time_rows,
            invalid_speed_rows,
            invalid_throttle_rows,
            invalid_rpm_rows,
            invalid_gear_rows,
        ) = row

        event_slug = str(
            event_slug
        )

        silver_events.add(
            event_slug
        )

        telemetry_rows = int(
            telemetry_rows or 0
        )

        drivers = int(
            drivers or 0
        )

        laps = int(
            laps or 0
        )

        invalid_driver_rows = int(
            invalid_driver_rows or 0
        )

        invalid_lap_rows = int(
            invalid_lap_rows or 0
        )

        invalid_sample_time_rows = int(
            invalid_sample_time_rows or 0
        )

        invalid_speed_rows = int(
            invalid_speed_rows or 0
        )

        invalid_throttle_rows = int(
            invalid_throttle_rows or 0
        )

        invalid_rpm_rows = int(
            invalid_rpm_rows or 0
        )

        invalid_gear_rows = int(
            invalid_gear_rows or 0
        )

        race_failures = []

        if telemetry_rows < min_rows:

            race_failures.append(
                f"only "
                f"{telemetry_rows:,} "
                f"telemetry rows"
            )

        if drivers < min_drivers:

            race_failures.append(
                f"only "
                f"{drivers} "
                f"drivers"
            )

        if laps < min_laps:

            race_failures.append(
                f"only "
                f"{laps} "
                f"laps"
            )

        if invalid_driver_rows > 0:

            race_failures.append(
                f"{invalid_driver_rows:,} "
                f"rows missing driver_code"
            )

        if invalid_lap_rows > 0:

            race_failures.append(
                f"{invalid_lap_rows:,} "
                f"rows missing lap_number"
            )

        if invalid_sample_time_rows > 0:

            race_failures.append(
                f"{invalid_sample_time_rows:,} "
                f"rows missing sample_time_ms"
            )

        if invalid_speed_rows > 0:

            race_failures.append(
                f"{invalid_speed_rows:,} "
                f"invalid speed rows"
            )

        if invalid_throttle_rows > 0:

            race_failures.append(
                f"{invalid_throttle_rows:,} "
                f"invalid throttle rows"
            )

        if invalid_rpm_rows > 0:

            race_failures.append(
                f"{invalid_rpm_rows:,} "
                f"invalid RPM rows"
            )

        if invalid_gear_rows > 0:

            race_failures.append(
                f"{invalid_gear_rows:,} "
                f"invalid gear rows"
            )

        if race_failures:

            status = "FAILED"

            for reason in race_failures:

                failures.append(
                    f"{event_slug}: "
                    f"{reason}"
                )

        else:

            status = "PASS"

        print(
            f"{event_slug:<32}"
            f"{telemetry_rows:>14,}"
            f"{drivers:>10}"
            f"{laps:>8}"
            f"{status:>12}"
        )

    # ========================================================
    # ROSTER CHECK
    # ========================================================

    print()
    print("=" * 110)
    print(
        "RACE ROSTER CHECK"
    )
    print("=" * 110)

    all_roster_events = sorted(
        set(
            results_drivers.keys()
        )
        |
        set(
            expected_drivers.keys()
        )
    )

    for event_slug in all_roster_events:

        roster = results_drivers.get(
            event_slug,
            set(),
        )

        lap_drivers = expected_drivers.get(
            event_slug,
            set(),
        )

        print(
            f"{event_slug:<32} "
            f"results={len(roster):>2} "
            f"with_laps={len(lap_drivers):>2}"
        )

        missing_from_laps = sorted(
            roster - lap_drivers
        )

        if missing_from_laps:

            print(
                "    Results-only drivers: "
                + ", ".join(
                    missing_from_laps
                )
            )

    # ========================================================
    # EXPECTED vs ACTUAL TELEMETRY
    # ========================================================

    print()
    print("=" * 110)
    print(
        "BRONZE LAPS vs SILVER TELEMETRY DRIVER COVERAGE"
    )
    print("=" * 110)

    all_events = sorted(
        set(
            expected_drivers.keys()
        )
        |
        set(
            actual_drivers.keys()
        )
    )

    for event_slug in all_events:

        expected = expected_drivers.get(
            event_slug,
            set(),
        )

        actual = actual_drivers.get(
            event_slug,
            set(),
        )

        missing = sorted(
            expected - actual
        )

        extra = sorted(
            actual - expected
        )

        if (
            event_slug
            in expected_drivers
            and event_slug
            not in actual_drivers
        ):

            failures.append(
                f"{event_slug}: "
                f"Bronze laps exist but "
                f"Silver telemetry is missing"
            )

            status = "FAILED"

        elif missing:

            failures.append(
                f"{event_slug}: "
                f"missing Silver telemetry "
                f"for drivers "
                f"{', '.join(missing)}"
            )

            status = "FAILED"

        else:

            status = "PASS"

        print(
            f"{event_slug:<32} "
            f"expected={len(expected):>2} "
            f"actual={len(actual):>2} "
            f"{status}"
        )

        if missing:

            print(
                "    Missing telemetry: "
                + ", ".join(
                    missing
                )
            )

        if extra:

            warnings.append(
                f"{event_slug}: "
                f"Silver telemetry contains "
                f"drivers not found in "
                f"bronze.laps: "
                f"{', '.join(extra)}"
            )

            print(
                "    Extra telemetry: "
                + ", ".join(
                    extra
                )
            )

    # ========================================================
    # DRIVER-LEVEL VOLUME
    # ========================================================

    print()
    print("=" * 110)
    print(
        "DRIVER-LEVEL TELEMETRY VOLUME"
    )
    print("=" * 110)

    low_volume_drivers = []

    for (
        event_slug,
        driver_code,
        telemetry_rows,
    ) in driver_metrics:

        telemetry_rows = int(
            telemetry_rows or 0
        )

        if (
            telemetry_rows
            < min_driver_rows
        ):

            low_volume_drivers.append(
                (
                    event_slug,
                    driver_code,
                    telemetry_rows,
                )
            )

            failures.append(
                f"{event_slug} / "
                f"{driver_code}: "
                f"only "
                f"{telemetry_rows:,} "
                f"telemetry rows"
            )

    if low_volume_drivers:

        for (
            event_slug,
            driver_code,
            telemetry_rows,
        ) in low_volume_drivers:

            print(
                f"FAILED | "
                f"{event_slug:<32} "
                f"{str(driver_code):<5} "
                f"{telemetry_rows:>10,} rows"
            )

    else:

        print(
            "PASS - All telemetry drivers "
            "meet minimum volume requirements."
        )

    # ========================================================
    # WARNINGS
    # ========================================================

    if warnings:

        print()
        print("=" * 110)
        print(
            "QUALITY WARNINGS"
        )
        print("=" * 110)

        for warning in warnings:

            print(
                f"WARNING: {warning}"
            )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    print()
    print("=" * 110)

    if failures:

        print(
            "TELEMETRY QUALITY GATE: FAILED"
        )

        print("=" * 110)

        print()

        print(
            f"Failures detected: "
            f"{len(failures)}"
        )

        print()

        for failure in failures:

            print(
                f"  - {failure}"
            )

        print()

        raise RuntimeError(
            "Silver telemetry failed "
            "quality validation."
        )

    print(
        "TELEMETRY QUALITY GATE: PASSED"
    )

    print("=" * 110)

    print()

    print(
        f"Silver races validated : "
        f"{len(race_metrics)}"
    )

    print(
        f"Bronze lap races checked: "
        f"{len(expected_drivers)}"
    )

    print()

    print(
        "All drivers represented in "
        "Bronze laps are present in "
        "Silver telemetry."
    )

    print()

    print(
        "Silver telemetry is safe "
        "for downstream analytics."
    )


# ============================================================
# CLI
# ============================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Validate Silver F1 telemetry "
            "before downstream analytics."
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
        "--min-rows",
        type=int,
        default=DEFAULT_MIN_ROWS,
    )

    parser.add_argument(
        "--min-drivers",
        type=int,
        default=DEFAULT_MIN_DRIVERS,
    )

    parser.add_argument(
        "--min-laps",
        type=int,
        default=DEFAULT_MIN_LAPS,
    )

    parser.add_argument(
        "--min-driver-rows",
        type=int,
        default=DEFAULT_MIN_DRIVER_ROWS,
    )

    args = parser.parse_args()

    try:

        validate_quality(
            year=args.year,
            session=args.session,
            min_rows=args.min_rows,
            min_drivers=args.min_drivers,
            min_laps=args.min_laps,
            min_driver_rows=args.min_driver_rows,
        )

    except Exception as exc:

        print()
        print(
            f"QUALITY GATE ERROR: "
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        sys.exit(1)


if __name__ == "__main__":
    main()
