{{
    config(
        materialized='incremental',
        incremental_strategy='append',
        tags=['externally_loaded']
    )
}}

{% set season = var('season', none) %}
{% set event_slug = var('event_slug', none) %}
{% set session_type = var('session_type', 'R') %}


with source_telemetry as (

    select *

    from {{ source('bronze', 'telemetry') }}

    where sample_timestamp_utc is not null
      and lap_number is not null
      and speed_kph between 0 and 400
      and throttle_pct between 0 and 100
      and rpm between 0 and 20000
      and gear between 0 and 8

    {#
       When Airflow supplies a race, only that Iceberg partition
       is scanned instead of the entire telemetry table.
    #}

    {% if season is not none %}
      and season = {{ season }}
    {% endif %}

    {% if event_slug is not none %}
      and event_slug = '{{ event_slug }}'
    {% endif %}

    {% if session_type is not none %}
      and session_type = '{{ session_type }}'
    {% endif %}

    {#
       On incremental runs, don't append the event again if it
       already exists in Silver.
    #}

    {% if is_incremental()
          and season is not none
          and event_slug is not none %}

      and not exists (

          select 1

          from {{ this }} existing

          where existing.season = {{ season }}
            and existing.event_slug = '{{ event_slug }}'
            and existing.session_type = '{{ session_type }}'

      )

    {% endif %}

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
