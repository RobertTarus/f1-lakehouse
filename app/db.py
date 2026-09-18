import os

import pandas as pd
import streamlit as st
from trino.dbapi import connect


# ============================================================
# TRINO CONNECTION SETTINGS
#
# Local defaults:
#     host    = localhost
#     port    = 8081
#     catalog = iceberg
#
# For deployment, these can be overridden with environment
# variables without changing the application code.
# ============================================================

TRINO_HOST = os.getenv("TRINO_HOST", "localhost")
TRINO_PORT = int(os.getenv("TRINO_PORT", "8081"))
TRINO_CATALOG = os.getenv("TRINO_CATALOG", "iceberg")
TRINO_USER = os.getenv("TRINO_USER", "f1_streamlit")
TRINO_HTTP_SCHEME = os.getenv("TRINO_HTTP_SCHEME", "http")


def get_connection(schema: str = "gold"):
    """
    Create a Trino connection.

    Parameters
    ----------
    schema:
        Iceberg schema to use for the session.
        Examples:
            gold
            silver
            bronze
    """

    return connect(
        host=TRINO_HOST,
        port=TRINO_PORT,
        user=TRINO_USER,
        catalog=TRINO_CATALOG,
        schema=schema,
        http_scheme=TRINO_HTTP_SCHEME,
    )


# ============================================================
# GENERIC QUERY
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def query_dataframe(
    sql: str,
    schema: str = "gold",
) -> pd.DataFrame:
    """
    Execute SQL against Trino and return a Pandas DataFrame.

    Results are cached for 5 minutes to reduce repeated queries
    when users interact with Streamlit widgets.
    """

    conn = get_connection(schema=schema)

    try:
        cursor = conn.cursor()

        cursor.execute(sql)

        rows = cursor.fetchall()

        columns = [
            column[0]
            for column in cursor.description
        ]

        return pd.DataFrame(
            rows,
            columns=columns,
        )

    finally:
        conn.close()


# ============================================================
# CONNECTION HEALTH
# ============================================================

@st.cache_data(ttl=60, show_spinner=False)
def check_connection() -> bool:
    """
    Check whether Trino is reachable.
    """

    try:
        df = query_dataframe(
            """
            SELECT 1 AS connection_test
            """
        )

        return (
            not df.empty
            and df.iloc[0]["connection_test"] == 1
        )

    except Exception:
        return False


# ============================================================
# AVAILABLE SEASONS
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def get_seasons() -> pd.DataFrame:
    """
    Return seasons available in the Gold telemetry model.
    """

    return query_dataframe(
        """
        SELECT DISTINCT
            season
        FROM gold.lap_telemetry_metrics
        ORDER BY season DESC
        """
    )


# ============================================================
# AVAILABLE RACES
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def get_races(
    season: int,
) -> pd.DataFrame:
    """
    Return races available for a given season.
    """

    season = int(season)

    return query_dataframe(
        f"""
        SELECT DISTINCT
            event_slug
        FROM gold.lap_telemetry_metrics
        WHERE season = {season}
          AND session_type = 'R'
        ORDER BY event_slug
        """
    )


# ============================================================
# AVAILABLE DRIVERS
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def get_drivers(
    season: int,
    event_slug: str,
) -> pd.DataFrame:
    """
    Return drivers available for a selected race.
    """

    season = int(season)

    safe_event_slug = event_slug.replace("'", "''")

    return query_dataframe(
        f"""
        SELECT DISTINCT
            driver_code,
            team_name
        FROM gold.lap_telemetry_metrics
        WHERE season = {season}
          AND event_slug = '{safe_event_slug}'
          AND session_type = 'R'
        ORDER BY
            team_name,
            driver_code
        """
    )


# ============================================================
# DRIVER LAPS
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def get_driver_laps(
    season: int,
    event_slug: str,
    driver_code: str,
) -> pd.DataFrame:
    """
    Return Gold lap metrics for one driver.
    """

    season = int(season)

    safe_event_slug = event_slug.replace("'", "''")
    safe_driver_code = driver_code.replace("'", "''")

    return query_dataframe(
        f"""
        SELECT
            *
        FROM gold.lap_telemetry_metrics
        WHERE season = {season}
          AND event_slug = '{safe_event_slug}'
          AND session_type = 'R'
          AND driver_code = '{safe_driver_code}'
        ORDER BY lap_number
        """
    )


# ============================================================
# SINGLE LAP TELEMETRY
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def get_lap_telemetry(
    season: int,
    event_slug: str,
    driver_code: str,
    lap_number: int,
) -> pd.DataFrame:
    """
    Return high-frequency Silver telemetry for one driver/lap.

    This powers:
        - speed trace
        - throttle trace
        - brake trace
        - RPM trace
        - DRS trace
        - XY circuit map
    """

    season = int(season)
    lap_number = int(lap_number)

    safe_event_slug = event_slug.replace("'", "''")
    safe_driver_code = driver_code.replace("'", "''")

    return query_dataframe(
        f"""
        SELECT
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
            distance_to_driver_ahead

        FROM silver.silver_telemetry

        WHERE season = {season}
          AND event_slug = '{safe_event_slug}'
          AND session_type = 'R'
          AND driver_code = '{safe_driver_code}'
          AND lap_number = {lap_number}

        ORDER BY sample_time_ms
        """,
        schema="silver",
    )


# ============================================================
# RACE SUMMARY
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def get_race_summary(
    season: int,
    event_slug: str,
) -> pd.DataFrame:
    """
    Return high-level race telemetry statistics.
    """

    season = int(season)

    safe_event_slug = event_slug.replace("'", "''")

    return query_dataframe(
        f"""
        SELECT

            COUNT(*) AS telemetry_laps,

            COUNT(
                DISTINCT driver_code
            ) AS drivers,

            SUM(
                telemetry_samples
            ) AS telemetry_samples,

            COUNT_IF(
                has_lap_record
            ) AS matched_laps,

            COUNT_IF(
                NOT has_lap_record
            ) AS unmatched_laps,

            ROUND(
                100.0
                * COUNT_IF(has_lap_record)
                / COUNT(*),
                2
            ) AS reconciliation_pct,

            COUNT_IF(
                has_lap_timing
            ) AS timed_laps,

            COUNT_IF(
                has_lap_record
                AND NOT has_lap_timing
            ) AS laps_without_timing

        FROM gold.lap_telemetry_metrics

        WHERE season = {season}
          AND event_slug = '{safe_event_slug}'
          AND session_type = 'R'
        """
    )


# ============================================================
# FASTEST LAPS
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def get_fastest_laps(
    season: int,
    event_slug: str,
) -> pd.DataFrame:
    """
    Return each driver's fastest valid timed lap.
    """

    season = int(season)

    safe_event_slug = event_slug.replace("'", "''")

    return query_dataframe(
        f"""
        WITH ranked AS (

            SELECT

                driver_code,
                team_name,
                lap_number,
                lap_time_seconds,
                compound,
                tyre_life,

                ROW_NUMBER() OVER (
                    PARTITION BY driver_code
                    ORDER BY lap_time_seconds
                ) AS lap_rank

            FROM gold.lap_telemetry_metrics

            WHERE season = {season}
              AND event_slug = '{safe_event_slug}'
              AND session_type = 'R'
              AND lap_time_seconds IS NOT NULL

        )

        SELECT

            driver_code,
            team_name,
            lap_number,
            lap_time_seconds,
            compound,
            tyre_life

        FROM ranked

        WHERE lap_rank = 1

        ORDER BY lap_time_seconds
        """
    )
