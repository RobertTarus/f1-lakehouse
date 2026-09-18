-- ============================================================
-- RACE DRIVER PERFORMANCE TIMING CONSISTENCY
--
-- avg_lap_seconds and fastest_lap_seconds may legitimately be
-- NULL when no usable timed laps exist.
--
-- However, when an average lap time exists:
--
--   - it must be positive
--   - fastest lap must exist
--   - fastest lap cannot be slower than the average lap
--
-- dbt singular tests pass when zero rows are returned.
-- ============================================================

select
    season,
    event_slug,
    session_type,
    driver_code,
    valid_laps,
    avg_lap_seconds,
    fastest_lap_seconds

from "iceberg"."gold"."race_driver_performance"

where
    (
        avg_lap_seconds is not null
        and avg_lap_seconds <= 0
    )

    or

    (
        avg_lap_seconds is not null
        and fastest_lap_seconds is null
    )

    or

    (
        fastest_lap_seconds is not null
        and fastest_lap_seconds <= 0
    )

    or

    (
        avg_lap_seconds is not null
        and fastest_lap_seconds is not null
        and fastest_lap_seconds > avg_lap_seconds
    )