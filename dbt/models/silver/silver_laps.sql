{{
    config(
        materialized='table',
        tags=['silver', 'laps']
    )
}}


-- ============================================================
-- SILVER: LAPS
--
-- Grain:
--     One row per:
--         season
--         event
--         session
--         driver
--         lap
--
-- Design principle:
--
--     Silver preserves legitimate source lap records.
--
--     We DO NOT remove a lap simply because:
--
--         - lap_time_ms is null
--         - lap_time_ms is zero
--         - is_accurate is false
--         - deleted is true
--
--     Instead, those conditions are retained as quality
--     attributes that downstream models can decide how to use.
--
-- This is important because telemetry may exist for a lap even
-- when FastF1 cannot provide a valid official lap time.
-- ============================================================


with source_laps as (

    select *

    from {{ source('bronze', 'laps') }}

),


-- ============================================================
-- NORMALIZE AND ADD QUALITY FLAGS
-- ============================================================

normalized as (

    select

        season,
        event_name,
        event_slug,
        session_type,

        driver_code,
        driver_number,
        team_name,

        lap_number,
        stint,
        position,

        lap_time_ms,

        case
            when lap_time_ms is not null
             and lap_time_ms > 0
            then round(
                lap_time_ms / 1000.0,
                3
            )
            else null
        end as lap_time_seconds,

        sector_1_ms,
        sector_2_ms,
        sector_3_ms,

        speed_i1,
        speed_i2,
        speed_fl,
        speed_st,

        upper(compound)
            as compound,

        tyre_life,
        fresh_tyre,

        track_status,

        is_personal_best,
        is_accurate,

        coalesce(
            deleted,
            false
        ) as is_deleted,

        lap_start_date,

        source_system,
        ingested_at,


        -- ----------------------------------------------------
        -- LAP TIMING FLAGS
        -- ----------------------------------------------------

        case
            when lap_time_ms is not null
             and lap_time_ms > 0
            then true
            else false
        end as has_lap_time,


        case
            when sector_1_ms is not null
             and sector_2_ms is not null
             and sector_3_ms is not null
            then true
            else false
        end as has_all_sectors,


        -- ----------------------------------------------------
        -- QUALITY CLASSIFICATION
        --
        -- A lap may still be kept in Silver even when its
        -- official timing is unsuitable for pace analysis.
        -- ----------------------------------------------------

        case

            when coalesce(
                deleted,
                false
            ) = true
            then 'DELETED'

            when is_accurate = false
            then 'INACCURATE'

            when lap_time_ms is null
            then 'NO_LAP_TIME'

            when lap_time_ms <= 0
            then 'INVALID_LAP_TIME'

            else 'VALID'

        end as lap_quality_status

    from source_laps

    -- Only remove records that cannot form the model grain.
    where season is not null
      and event_slug is not null
      and session_type is not null
      and driver_code is not null
      and lap_number is not null

),


-- ============================================================
-- DEDUPLICATE
--
-- If a race is re-ingested, keep the latest version of each
-- driver/lap record.
-- ============================================================

ranked as (

    select

        *,

        row_number() over (

            partition by

                season,
                event_slug,
                session_type,
                driver_code,
                lap_number

            order by

                ingested_at desc

        ) as record_rank

    from normalized

),


deduplicated as (

    select

        season,
        event_name,
        event_slug,
        session_type,

        driver_code,
        driver_number,
        team_name,

        lap_number,
        stint,
        position,

        lap_time_ms,
        lap_time_seconds,

        sector_1_ms,
        sector_2_ms,
        sector_3_ms,

        speed_i1,
        speed_i2,
        speed_fl,
        speed_st,

        compound,

        tyre_life,
        fresh_tyre,

        track_status,

        is_personal_best,
        is_accurate,
        is_deleted,

        has_lap_time,
        has_all_sectors,
        lap_quality_status,

        lap_start_date,

        source_system,
        ingested_at

    from ranked

    where record_rank = 1

)


-- ============================================================
-- FINAL SILVER MODEL
-- ============================================================

select *

from deduplicated
