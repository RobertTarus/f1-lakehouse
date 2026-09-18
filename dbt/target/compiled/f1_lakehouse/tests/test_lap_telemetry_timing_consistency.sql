-- ============================================================
-- LAP TIMING CONSISTENCY
--
-- If has_lap_timing is true, lap_time_seconds must exist.
--
-- If lap_time_seconds exists, has_lap_timing must be true.
-- ============================================================

select

    season,
    event_slug,
    session_type,
    driver_code,
    lap_number,
    lap_time_seconds,
    has_lap_timing,
    lap_match_status

from "iceberg"."gold"."lap_telemetry_metrics"

where

    (
        has_lap_timing = true
        and lap_time_seconds is null
    )

    or

    (
        lap_time_seconds is not null
        and has_lap_timing = false
    )

    or

    (
        has_lap_timing = true
        and lap_match_status
            <> 'MATCHED_WITH_LAP_TIME'
    )

    or

    (
        has_lap_record = true
        and has_lap_timing = false
        and lap_match_status
            <> 'MATCHED_NO_LAP_TIME'
    )