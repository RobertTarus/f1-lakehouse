-- ============================================================
-- GOLD TELEMETRY METRIC RANGE VALIDATION
--
-- Any returned row represents an invalid analytical metric.
-- ============================================================

select *

from "iceberg"."gold"."lap_telemetry_metrics"

where

    telemetry_samples <= 0

    or (
        avg_speed_kph is not null
        and (
            avg_speed_kph < 0
            or avg_speed_kph > 400
        )
    )

    or (
        min_speed_kph is not null
        and (
            min_speed_kph < 0
            or min_speed_kph > 400
        )
    )

    or (
        max_speed_kph is not null
        and (
            max_speed_kph < 0
            or max_speed_kph > 400
        )
    )

    or (
        avg_rpm is not null
        and (
            avg_rpm < 0
            or avg_rpm > 20000
        )
    )

    or (
        peak_rpm is not null
        and (
            peak_rpm < 0
            or peak_rpm > 20000
        )
    )

    or (
        avg_throttle_pct is not null
        and (
            avg_throttle_pct < 0
            or avg_throttle_pct > 100
        )
    )

    or (
        full_throttle_pct is not null
        and (
            full_throttle_pct < 0
            or full_throttle_pct > 100
        )
    )

    or (
        low_throttle_pct is not null
        and (
            low_throttle_pct < 0
            or low_throttle_pct > 100
        )
    )

    or (
        braking_pct is not null
        and (
            braking_pct < 0
            or braking_pct > 100
        )
    )

    or (
        drs_usage_pct is not null
        and (
            drs_usage_pct < 0
            or drs_usage_pct > 100
        )
    )

    or (
        avg_gear is not null
        and (
            avg_gear < 0
            or avg_gear > 8
        )
    )

    or (
        min_gear is not null
        and (
            min_gear < 0
            or min_gear > 8
        )
    )

    or (
        max_gear is not null
        and (
            max_gear < 0
            or max_gear > 8
        )
    )

    or (
        telemetry_duration_ms is not null
        and telemetry_duration_ms < 0
    )

    or (
        telemetry_distance_m is not null
        and telemetry_distance_m < 0
    )