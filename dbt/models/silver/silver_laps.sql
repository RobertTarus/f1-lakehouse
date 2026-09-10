{{ config(
    materialized='table'
) }}

with source_laps as (

    select *
    from {{ source('bronze', 'laps') }}

),

valid_laps as (

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

        round(
            lap_time_ms / 1000.0,
            3
        ) as lap_time_seconds,

        sector_1_ms,
        sector_2_ms,
        sector_3_ms,

        speed_i1,
        speed_i2,
        speed_fl,
        speed_st,

        upper(compound) as compound,

        tyre_life,
        fresh_tyre,

        track_status,

        is_personal_best,
        is_accurate,

        lap_start_date,

        source_system,
        ingested_at

    from source_laps

    where lap_time_ms is not null
      and lap_time_ms > 0
      and is_accurate = true
      and coalesce(deleted, false) = false

)

select *
from valid_laps
