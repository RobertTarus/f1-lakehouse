
  
    

    create table "iceberg"."silver"."silver_telemetry__dbt_tmp"
      
      
    as (
      

with source_telemetry as (

    select *

    from "iceberg"."bronze"."telemetry"

),

validated as (

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
        distance_to_driver_ahead,

        source,
        status,

        source_system,
        ingested_at,

        row_number() over (

            partition by
                season,
                event_slug,
                session_type,
                driver_code,
                lap_number,
                sample_time_ms

            order by sample_timestamp_utc

        ) as telemetry_record_number

    from source_telemetry

    where sample_timestamp_utc is not null

      and lap_number is not null

      and speed_kph between 0 and 400

      and throttle_pct between 0 and 100

      and rpm between 0 and 20000

      and gear between 0 and 8

),

deduplicated as (

    select *

    from validated

    where telemetry_record_number = 1

)

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
    distance_to_driver_ahead,

    source,
    status,

    source_system,
    ingested_at

from deduplicated
    );

  