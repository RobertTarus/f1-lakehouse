{{ config(materialized='table') }}

with source_weather as (

    select *
    from {{ source('bronze', 'weather') }}

),

cleaned as (

    select
        season,
        event_name,
        event_slug,
        session_type,

        session_time_ms,

        air_temp_c,
        track_temp_c,
        humidity_pct,
        pressure_mbar,

        rainfall,

        wind_direction_deg,
        wind_speed,

        source_system,
        ingested_at

    from source_weather

    where season is not null
      and event_slug is not null
      and session_time_ms is not null
)

select *
from cleaned
