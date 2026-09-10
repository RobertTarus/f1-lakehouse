

with source_results as (

    select *
    from "iceberg"."bronze"."results"

),

cleaned as (

    select
        season,
        event_name,
        event_slug,
        session_type,

        driver_number,
        driver_code,
        driver_id,

        first_name,
        last_name,
        full_name,
        country_code,

        team_name,
        team_id,

        position,
        classified_position,
        grid_position,

        status,
        points,
        result_time_ms,

        source_system,
        ingested_at

    from source_results

    where driver_code is not null
      and season is not null
      and event_slug is not null
)

select *
from cleaned