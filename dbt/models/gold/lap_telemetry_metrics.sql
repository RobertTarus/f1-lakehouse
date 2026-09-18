{{
    config(
        materialized='table',
        tags=['gold', 'telemetry']
    )
}}


-- ============================================================
-- GOLD: LAP TELEMETRY METRICS
--
-- Grain:
--     One row per:
--         season
--         event
--         session
--         driver
--         lap
--
-- Sources:
--     silver_telemetry
--     silver_laps
--
-- Purpose:
--     Aggregate high-volume telemetry samples into
--     analytics-ready lap-level metrics and enrich them
--     with lap timing, tyre and race-position information.
--
-- Important:
--     has_lap_record = telemetry lap successfully matched
--                      to a record in silver_laps
--
--     has_lap_timing = matched lap has a non-null lap time
--
-- These are intentionally separate concepts.
-- ============================================================


with telemetry as (

    select

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
        distance_to_driver_ahead

    from {{ ref('silver_telemetry') }}

    where lap_number is not null
      and driver_code is not null

),


-- ============================================================
-- AGGREGATE TELEMETRY TO DRIVER / LAP GRAIN
-- ============================================================

lap_metrics as (

    select

        season,
        event_name,
        event_slug,
        session_type,

        driver_code,

        max(driver_number)
            as driver_number,

        max(team_name)
            as team_name,

        lap_number,


        -- ----------------------------------------------------
        -- TELEMETRY COVERAGE
        -- ----------------------------------------------------

        count(*)
            as telemetry_samples,

        min(sample_timestamp_utc)
            as first_sample_timestamp_utc,

        max(sample_timestamp_utc)
            as last_sample_timestamp_utc,

        min(session_time_ms)
            as telemetry_start_ms,

        max(session_time_ms)
            as telemetry_end_ms,

        max(session_time_ms)
            - min(session_time_ms)
            as telemetry_duration_ms,


        -- ----------------------------------------------------
        -- SPEED
        -- ----------------------------------------------------

        round(
            avg(speed_kph),
            2
        ) as avg_speed_kph,

        round(
            min(speed_kph),
            2
        ) as min_speed_kph,

        round(
            max(speed_kph),
            2
        ) as max_speed_kph,

        round(
            approx_percentile(
                speed_kph,
                0.50
            ),
            2
        ) as median_speed_kph,

        round(
            approx_percentile(
                speed_kph,
                0.95
            ),
            2
        ) as p95_speed_kph,


        -- ----------------------------------------------------
        -- RPM
        -- ----------------------------------------------------

        round(
            avg(rpm),
            0
        ) as avg_rpm,

        round(
            max(rpm),
            0
        ) as peak_rpm,

        round(
            approx_percentile(
                rpm,
                0.95
            ),
            0
        ) as p95_rpm,


        -- ----------------------------------------------------
        -- THROTTLE
        -- ----------------------------------------------------

        round(
            avg(throttle_pct),
            2
        ) as avg_throttle_pct,

        round(
            100.0
            * avg(
                case
                    when throttle_pct >= 99
                    then 1.0
                    else 0.0
                end
            ),
            2
        ) as full_throttle_pct,

        round(
            100.0
            * avg(
                case
                    when throttle_pct <= 10
                    then 1.0
                    else 0.0
                end
            ),
            2
        ) as low_throttle_pct,


        -- ----------------------------------------------------
        -- BRAKING
        -- ----------------------------------------------------

        sum(
            case
                when brake
                then 1
                else 0
            end
        ) as braking_samples,

        round(
            100.0
            * avg(
                case
                    when brake
                    then 1.0
                    else 0.0
                end
            ),
            2
        ) as braking_pct,


        -- ----------------------------------------------------
        -- DRS
        --
        -- FastF1 DRS states >= 10 represent active/open
        -- states.
        -- ----------------------------------------------------

        sum(
            case
                when drs >= 10
                then 1
                else 0
            end
        ) as drs_active_samples,

        round(
            100.0
            * avg(
                case
                    when drs >= 10
                    then 1.0
                    else 0.0
                end
            ),
            2
        ) as drs_usage_pct,


        -- ----------------------------------------------------
        -- GEAR
        -- ----------------------------------------------------

        round(
            avg(
                cast(
                    gear as double
                )
            ),
            2
        ) as avg_gear,

        min(gear)
            as min_gear,

        max(gear)
            as max_gear,


        -- ----------------------------------------------------
        -- DISTANCE
        -- ----------------------------------------------------

        round(
            max(distance),
            2
        ) as measured_lap_distance,

        round(
            max(distance)
            - min(distance),
            2
        ) as telemetry_distance_m,

        round(
            max(relative_distance),
            6
        ) as max_relative_distance,


        -- ----------------------------------------------------
        -- TRAFFIC
        -- ----------------------------------------------------

        round(
            avg(
                distance_to_driver_ahead
            ),
            2
        ) as avg_distance_to_driver_ahead_m,

        round(
            min(
                distance_to_driver_ahead
            ),
            2
        ) as min_distance_to_driver_ahead_m,

        count(
            distinct driver_ahead
        ) as distinct_drivers_ahead,


        -- ----------------------------------------------------
        -- TELEMETRY QUALITY INFORMATION
        -- ----------------------------------------------------

        count_if(
            speed_kph is null
        ) as null_speed_samples,

        count_if(
            rpm is null
        ) as null_rpm_samples,

        count_if(
            throttle_pct is null
        ) as null_throttle_samples,

        count_if(
            gear is null
        ) as null_gear_samples

    from telemetry

    group by

        season,
        event_name,
        event_slug,
        session_type,
        driver_code,
        lap_number

),


-- ============================================================
-- SILVER LAP DATA
--
-- lap_record_exists is deliberately separate from
-- lap_time_seconds.
--
-- A lap may exist in silver_laps even when FastF1 does not
-- provide a valid lap time.
-- ============================================================

laps as (

    select

        season,
        event_slug,
        session_type,

        driver_code,
        lap_number,

        lap_time_seconds,
        compound,
        tyre_life,
        position,

        true as lap_record_exists

    from {{ ref('silver_laps') }}

    where lap_number is not null
      and driver_code is not null

),


-- ============================================================
-- JOIN TELEMETRY TO LAP DATA
-- ============================================================

combined as (

    select

        t.season,
        t.event_name,
        t.event_slug,
        t.session_type,

        t.driver_code,
        t.driver_number,
        t.team_name,

        t.lap_number,


        -- ----------------------------------------------------
        -- LAP INFORMATION
        -- ----------------------------------------------------

        l.lap_time_seconds,
        l.compound,
        l.tyre_life,
        l.position,


        -- ----------------------------------------------------
        -- TELEMETRY COVERAGE
        -- ----------------------------------------------------

        t.telemetry_samples,

        t.first_sample_timestamp_utc,
        t.last_sample_timestamp_utc,

        t.telemetry_start_ms,
        t.telemetry_end_ms,

        t.telemetry_duration_ms,

        round(
            t.telemetry_duration_ms
            / 1000.0,
            3
        ) as telemetry_duration_seconds,


        -- ----------------------------------------------------
        -- SPEED
        -- ----------------------------------------------------

        t.avg_speed_kph,
        t.min_speed_kph,
        t.max_speed_kph,
        t.median_speed_kph,
        t.p95_speed_kph,


        -- ----------------------------------------------------
        -- ENGINE
        -- ----------------------------------------------------

        t.avg_rpm,
        t.peak_rpm,
        t.p95_rpm,


        -- ----------------------------------------------------
        -- THROTTLE
        -- ----------------------------------------------------

        t.avg_throttle_pct,
        t.full_throttle_pct,
        t.low_throttle_pct,


        -- ----------------------------------------------------
        -- BRAKING
        -- ----------------------------------------------------

        t.braking_samples,
        t.braking_pct,


        -- ----------------------------------------------------
        -- DRS
        -- ----------------------------------------------------

        t.drs_active_samples,
        t.drs_usage_pct,


        -- ----------------------------------------------------
        -- GEAR
        -- ----------------------------------------------------

        t.avg_gear,
        t.min_gear,
        t.max_gear,


        -- ----------------------------------------------------
        -- DISTANCE
        -- ----------------------------------------------------

        t.measured_lap_distance,
        t.telemetry_distance_m,
        t.max_relative_distance,


        -- ----------------------------------------------------
        -- TRAFFIC
        -- ----------------------------------------------------

        t.avg_distance_to_driver_ahead_m,
        t.min_distance_to_driver_ahead_m,
        t.distinct_drivers_ahead,


        -- ----------------------------------------------------
        -- SAMPLE QUALITY
        -- ----------------------------------------------------

        t.null_speed_samples,
        t.null_rpm_samples,
        t.null_throttle_samples,
        t.null_gear_samples,


        -- ----------------------------------------------------
        -- LAP JOIN QUALITY
        --
        -- has_lap_record:
        --     Did this telemetry lap match silver_laps?
        --
        -- has_lap_timing:
        --     Does that matched lap have a valid lap time?
        -- ----------------------------------------------------

        case
            when l.lap_record_exists is true
            then true
            else false
        end as has_lap_record,

        case
            when l.lap_time_seconds is not null
            then true
            else false
        end as has_lap_timing,


        -- ----------------------------------------------------
        -- HUMAN-READABLE MATCH STATUS
        -- ----------------------------------------------------

        case

            when l.lap_record_exists is null
            then 'NO_LAP_RECORD'

            when l.lap_time_seconds is null
            then 'MATCHED_NO_LAP_TIME'

            else 'MATCHED_WITH_LAP_TIME'

        end as lap_match_status

    from lap_metrics t

    left join laps l

        on t.season = l.season

       and t.event_slug = l.event_slug

       and t.session_type = l.session_type

       and t.driver_code = l.driver_code

       and t.lap_number = l.lap_number

)


-- ============================================================
-- FINAL GOLD MODEL
-- ============================================================

select

    season,
    event_name,
    event_slug,
    session_type,

    driver_code,
    driver_number,
    team_name,

    lap_number,


    -- --------------------------------------------------------
    -- LAP DATA
    -- --------------------------------------------------------

    lap_time_seconds,
    compound,
    tyre_life,
    position,


    -- --------------------------------------------------------
    -- TELEMETRY COVERAGE
    -- --------------------------------------------------------

    telemetry_samples,

    first_sample_timestamp_utc,
    last_sample_timestamp_utc,

    telemetry_start_ms,
    telemetry_end_ms,

    telemetry_duration_ms,
    telemetry_duration_seconds,


    -- --------------------------------------------------------
    -- SPEED
    -- --------------------------------------------------------

    avg_speed_kph,
    min_speed_kph,
    max_speed_kph,
    median_speed_kph,
    p95_speed_kph,


    -- --------------------------------------------------------
    -- ENGINE
    -- --------------------------------------------------------

    avg_rpm,
    peak_rpm,
    p95_rpm,


    -- --------------------------------------------------------
    -- THROTTLE
    -- --------------------------------------------------------

    avg_throttle_pct,
    full_throttle_pct,
    low_throttle_pct,


    -- --------------------------------------------------------
    -- BRAKING
    -- --------------------------------------------------------

    braking_samples,
    braking_pct,


    -- --------------------------------------------------------
    -- DRS
    -- --------------------------------------------------------

    drs_active_samples,
    drs_usage_pct,


    -- --------------------------------------------------------
    -- GEAR
    -- --------------------------------------------------------

    avg_gear,
    min_gear,
    max_gear,


    -- --------------------------------------------------------
    -- DISTANCE
    -- --------------------------------------------------------

    measured_lap_distance,
    telemetry_distance_m,
    max_relative_distance,


    -- --------------------------------------------------------
    -- TRAFFIC
    -- --------------------------------------------------------

    avg_distance_to_driver_ahead_m,
    min_distance_to_driver_ahead_m,
    distinct_drivers_ahead,


    -- --------------------------------------------------------
    -- TELEMETRY QUALITY
    -- --------------------------------------------------------

    null_speed_samples,
    null_rpm_samples,
    null_throttle_samples,
    null_gear_samples,


    -- --------------------------------------------------------
    -- LAP MATCH QUALITY
    -- --------------------------------------------------------

    has_lap_record,
    has_lap_timing,
    lap_match_status,


    -- --------------------------------------------------------
    -- LINEAGE
    -- --------------------------------------------------------

    current_timestamp
        as gold_generated_at

from combined
