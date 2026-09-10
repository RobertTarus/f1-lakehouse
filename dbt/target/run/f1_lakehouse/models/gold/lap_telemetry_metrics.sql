
  
    

    create table "iceberg"."gold"."lap_telemetry_metrics__dbt_tmp"
      
      
    as (
      

with telemetry as (

    select *

    from "iceberg"."silver"."silver_telemetry"

),

lap_metrics as (

    select

        season,
        event_name,
        event_slug,
        session_type,

        driver_code,
        team_name,
        lap_number,

        count(*) as telemetry_samples,

        round(
            avg(speed_kph),
            2
        ) as avg_speed_kph,

        round(
            max(speed_kph),
            2
        ) as max_speed_kph,

        round(
            avg(rpm),
            0
        ) as avg_rpm,

        round(
            max(rpm),
            0
        ) as peak_rpm,

        round(
            avg(throttle_pct),
            2
        ) as avg_throttle_pct,

        round(
            100.0
            * sum(
                case
                    when throttle_pct >= 99
                    then 1
                    else 0
                end
            )
            / count(*),
            2
        ) as full_throttle_pct,

        round(
            100.0
            * sum(
                case
                    when brake
                    then 1
                    else 0
                end
            )
            / count(*),
            2
        ) as braking_pct,

        round(
            max(distance),
            2
        ) as measured_lap_distance

    from telemetry

    group by

        season,
        event_name,
        event_slug,
        session_type,

        driver_code,
        team_name,
        lap_number

),

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
        position

    from "iceberg"."silver"."silver_laps"

)

select

    t.season,
    t.event_name,
    t.event_slug,
    t.session_type,

    t.driver_code,
    t.team_name,
    t.lap_number,

    l.lap_time_seconds,
    l.compound,
    l.tyre_life,
    l.position,

    t.telemetry_samples,

    t.avg_speed_kph,
    t.max_speed_kph,

    t.avg_rpm,
    t.peak_rpm,

    t.avg_throttle_pct,
    t.full_throttle_pct,
    t.braking_pct,

    t.measured_lap_distance

from lap_metrics t

left join laps l

    on t.season = l.season

   and t.event_slug = l.event_slug

   and t.session_type = l.session_type

   and t.driver_code = l.driver_code

   and t.lap_number = l.lap_number
    );

  