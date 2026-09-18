from __future__ import annotations

import argparse
import os

from trino.dbapi import connect


def run_sql(cursor, sql: str):
    """
    Execute SQL and print it to the task log.

    Statements such as CREATE, DELETE, and INSERT may not
    return rows, so fetch failures are treated as an empty
    result set.
    """

    print("\n" + "=" * 70)
    print(sql.strip())
    print("=" * 70)

    cursor.execute(sql)

    try:
        return cursor.fetchall()
    except Exception:
        return []


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Load one race of Bronze telemetry into Silver."
        )
    )

    parser.add_argument(
        "--year",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--event-slug",
        required=True,
    )

    parser.add_argument(
        "--session",
        default="R",
    )

    args = parser.parse_args()

    season = int(args.year)

    event_slug = (
        args.event_slug.replace(
            "'",
            "''",
        )
    )

    session_type = (
        args.session.replace(
            "'",
            "''",
        )
    )

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

    connection = connect(
        host=host,
        port=port,
        user="f1_silver_telemetry_loader",
        catalog="iceberg",
        schema="silver",
        http_scheme="http",
    )

    cursor = connection.cursor()

    try:

        # ============================================================
        # 1. VERIFY BRONZE TELEMETRY EXISTS
        # ============================================================

        bronze_check = f"""
            SELECT COUNT(*)
            FROM iceberg.bronze.telemetry
            WHERE season = {season}
              AND event_slug = '{event_slug}'
              AND session_type = '{session_type}'
        """

        rows = run_sql(
            cursor,
            bronze_check,
        )

        bronze_count = (
            int(rows[0][0])
            if rows
            else 0
        )

        print()
        print(
            f"Bronze telemetry rows: "
            f"{bronze_count:,}"
        )

        if bronze_count == 0:

            raise RuntimeError(
                f"No Bronze telemetry found for "
                f"{season}/"
                f"{event_slug}/"
                f"{session_type}"
            )

        # ============================================================
        # 2. VERIFY DRIVER COMPLETENESS
        #
        # bronze.laps represents the expected race driver population.
        #
        # This prevents a partially promoted Bronze telemetry race
        # from being loaded into Silver.
        # ============================================================

        expected_drivers_sql = f"""
            SELECT COUNT(DISTINCT driver_code)
            FROM iceberg.bronze.laps
            WHERE season = {season}
              AND event_slug = '{event_slug}'
              AND session_type = '{session_type}'
              AND driver_code IS NOT NULL
        """

        telemetry_drivers_sql = f"""
            SELECT COUNT(DISTINCT driver_code)
            FROM iceberg.bronze.telemetry
            WHERE season = {season}
              AND event_slug = '{event_slug}'
              AND session_type = '{session_type}'
              AND driver_code IS NOT NULL
        """

        expected_rows = run_sql(
            cursor,
            expected_drivers_sql,
        )

        telemetry_rows = run_sql(
            cursor,
            telemetry_drivers_sql,
        )

        expected_drivers = (
            int(expected_rows[0][0])
            if expected_rows
            else 0
        )

        telemetry_drivers = (
            int(telemetry_rows[0][0])
            if telemetry_rows
            else 0
        )

        print()
        print("=" * 70)
        print("BRONZE DRIVER COMPLETENESS")
        print("=" * 70)

        print(
            f"Expected drivers  : "
            f"{expected_drivers}"
        )

        print(
            f"Telemetry drivers : "
            f"{telemetry_drivers}"
        )

        print("=" * 70)

        if expected_drivers == 0:

            raise RuntimeError(
                f"No Bronze lap drivers found for "
                f"{season}/"
                f"{event_slug}/"
                f"{session_type}"
            )

        if (
            telemetry_drivers
            != expected_drivers
        ):

            missing_drivers_sql = f"""
                SELECT DISTINCT driver_code
                FROM iceberg.bronze.laps
                WHERE season = {season}
                  AND event_slug = '{event_slug}'
                  AND session_type = '{session_type}'
                  AND driver_code IS NOT NULL

                EXCEPT

                SELECT DISTINCT driver_code
                FROM iceberg.bronze.telemetry
                WHERE season = {season}
                  AND event_slug = '{event_slug}'
                  AND session_type = '{session_type}'
                  AND driver_code IS NOT NULL

                ORDER BY driver_code
            """

            missing_rows = run_sql(
                cursor,
                missing_drivers_sql,
            )

            missing_drivers = [
                row[0]
                for row in missing_rows
            ]

            raise RuntimeError(
                "Bronze telemetry is incomplete. "
                f"Expected {expected_drivers} drivers "
                f"but found {telemetry_drivers}. "
                f"Missing drivers: "
                f"{missing_drivers}"
            )

        # ============================================================
        # 3. CREATE SILVER SCHEMA
        #
        # Required for a completely fresh lakehouse.
        # ============================================================

        create_schema_sql = """
            CREATE SCHEMA IF NOT EXISTS iceberg.silver
        """

        run_sql(
            cursor,
            create_schema_sql,
        )

        # ============================================================
        # 4. CREATE SILVER TELEMETRY TABLE
        #
        # This makes the loader cold-start safe.
        #
        # The schema intentionally mirrors the validated telemetry
        # columns that are written by this loader.
        # ============================================================

        create_table_sql = """
            CREATE TABLE IF NOT EXISTS
                iceberg.silver.silver_telemetry
            (
                season INTEGER,
                event_name VARCHAR,
                event_slug VARCHAR,
                session_type VARCHAR,

                driver_code VARCHAR,
                driver_number VARCHAR,
                team_name VARCHAR,
                lap_number INTEGER,

                sample_timestamp_utc
                    TIMESTAMP(6) WITH TIME ZONE,

                session_time_ms BIGINT,
                sample_time_ms BIGINT,

                rpm DOUBLE,
                speed_kph DOUBLE,
                gear INTEGER,
                throttle_pct DOUBLE,
                brake BOOLEAN,
                drs INTEGER,

                x DOUBLE,
                y DOUBLE,
                z DOUBLE,

                distance DOUBLE,
                relative_distance DOUBLE,

                driver_ahead VARCHAR,
                distance_to_driver_ahead DOUBLE,

                source VARCHAR,
                status VARCHAR,

                source_system VARCHAR,

                ingested_at
                    TIMESTAMP(6) WITH TIME ZONE
            )
            WITH (
                partitioning = ARRAY[
                    'season',
                    'event_slug',
                    'session_type',
                    'driver_code'
                ]
            )
        """

        run_sql(
            cursor,
            create_table_sql,
        )

        # ============================================================
        # 5. DELETE EXISTING SILVER PARTITION
        #
        # Makes each race load idempotent.
        # ============================================================

        delete_sql = f"""
            DELETE FROM iceberg.silver.silver_telemetry
            WHERE season = {season}
              AND event_slug = '{event_slug}'
              AND session_type = '{session_type}'
        """

        run_sql(
            cursor,
            delete_sql,
        )

        # ============================================================
        # 6. TRANSFORM ONLY THIS RACE
        # ============================================================

        insert_sql = f"""
            INSERT INTO iceberg.silver.silver_telemetry

            WITH validated AS (

                SELECT

                    season,
                    event_name,
                    event_slug,
                    session_type,

                    driver_code,
                    driver_number,
                    team_name,
                    lap_number,

                    sample_timestamp_utc,
                    session_time_ms,
                    sample_time_ms,

                    rpm,
                    speed_kph,
                    gear,
                    throttle_pct,
                    brake,
                    drs,

                    x,
                    y,
                    z,

                    distance,
                    relative_distance,

                    driver_ahead,
                    distance_to_driver_ahead,

                    source,
                    status,

                    source_system,
                    ingested_at,

                    row_number() OVER (

                        PARTITION BY

                            season,
                            event_slug,
                            session_type,
                            driver_code,
                            lap_number,
                            sample_time_ms

                        ORDER BY
                            sample_timestamp_utc

                    ) AS telemetry_record_number

                FROM iceberg.bronze.telemetry

                WHERE season = {season}

                  AND event_slug = '{event_slug}'

                  AND session_type = '{session_type}'

                  AND sample_timestamp_utc
                      IS NOT NULL

                  AND lap_number
                      IS NOT NULL

                  AND speed_kph
                      BETWEEN 0 AND 400

                  AND throttle_pct
                      BETWEEN 0 AND 100

                  AND rpm
                      BETWEEN 0 AND 20000

                  AND gear
                      BETWEEN 0 AND 8
            )

            SELECT

                season,
                event_name,
                event_slug,
                session_type,

                driver_code,
                driver_number,
                team_name,
                lap_number,

                sample_timestamp_utc,
                session_time_ms,
                sample_time_ms,

                rpm,
                speed_kph,
                gear,
                throttle_pct,
                brake,
                drs,

                x,
                y,
                z,

                distance,
                relative_distance,

                driver_ahead,
                distance_to_driver_ahead,

                source,
                status,

                source_system,
                ingested_at

            FROM validated

            WHERE telemetry_record_number = 1
        """

        run_sql(
            cursor,
            insert_sql,
        )

        # ============================================================
        # 7. VALIDATE SILVER PARTITION
        # ============================================================

        validation_sql = f"""
            SELECT

                event_slug,

                COUNT(*) AS telemetry_rows,

                COUNT(
                    DISTINCT driver_code
                ) AS drivers,

                COUNT(
                    DISTINCT lap_number
                ) AS laps

            FROM iceberg.silver.silver_telemetry

            WHERE season = {season}

              AND event_slug = '{event_slug}'

              AND session_type = '{session_type}'

            GROUP BY event_slug
        """

        results = run_sql(
            cursor,
            validation_sql,
        )

        if not results:

            raise RuntimeError(
                "Silver telemetry validation "
                "returned no rows."
            )

        (
            event,
            row_count,
            drivers,
            laps,
        ) = results[0]

        # ============================================================
        # 8. POST-LOAD DRIVER VALIDATION
        # ============================================================

        if int(drivers) != telemetry_drivers:

            raise RuntimeError(
                "Silver telemetry driver count "
                "does not match Bronze. "
                f"Bronze={telemetry_drivers}, "
                f"Silver={drivers}"
            )

        print()
        print("SUCCESS")
        print("=" * 70)

        print(
            f"Event          : "
            f"{event}"
        )

        print(
            f"Telemetry rows : "
            f"{row_count:,}"
        )

        print(
            f"Drivers        : "
            f"{drivers}"
        )

        print(
            f"Laps           : "
            f"{laps}"
        )

        print("=" * 70)

    finally:

        cursor.close()
        connection.close()


if __name__ == "__main__":
    main()
