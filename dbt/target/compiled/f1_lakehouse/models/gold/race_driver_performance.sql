

with lap_metrics as (

    select
        season,
        event_name,
        event_slug,
        session_type,
        driver_code,
        team_name,

        count(*) as valid_laps,

        round(
            avg(lap_time_seconds),
            3
        ) as avg_lap_seconds,

        round(
            min(lap_time_seconds),
            3
        ) as fastest_lap_seconds,

        round(
            max(lap_time_seconds),
            3
        ) as slowest_lap_seconds,

        round(
            avg(sector_1_ms) / 1000.0,
            3
        ) as avg_sector_1_seconds,

        round(
            avg(sector_2_ms) / 1000.0,
            3
        ) as avg_sector_2_seconds,

        round(
            avg(sector_3_ms) / 1000.0,
            3
        ) as avg_sector_3_seconds,

        round(
            avg(tyre_life),
            2
        ) as avg_tyre_life

    from "iceberg"."silver"."silver_laps"

    group by
        season,
        event_name,
        event_slug,
        session_type,
        driver_code,
        team_name
),

results as (

    select
        season,
        event_slug,
        session_type,
        driver_code,

        full_name,
        grid_position,
        position as finish_position,
        classified_position,
        points,
        status

    from "iceberg"."silver"."silver_results"

),

weather as (

    select
        season,
        event_slug,
        session_type,

        round(avg(air_temp_c), 2)
            as avg_air_temp_c,

        round(avg(track_temp_c), 2)
            as avg_track_temp_c,

        round(avg(humidity_pct), 2)
            as avg_humidity_pct,

        round(avg(wind_speed), 2)
            as avg_wind_speed,

        max(
            case
                when rainfall then 1
                else 0
            end
        ) as rain_detected

    from "iceberg"."silver"."silver_weather"

    group by
        season,
        event_slug,
        session_type
)

select
    l.season,
    l.event_name,
    l.event_slug,
    l.session_type,

    l.driver_code,
    r.full_name,
    l.team_name,

    r.grid_position,
    r.finish_position,

    (
        r.grid_position - r.finish_position
    ) as positions_gained,

    r.points,
    r.status,

    l.valid_laps,
    l.avg_lap_seconds,
    l.fastest_lap_seconds,
    l.slowest_lap_seconds,

    l.avg_sector_1_seconds,
    l.avg_sector_2_seconds,
    l.avg_sector_3_seconds,

    l.avg_tyre_life,

    w.avg_air_temp_c,
    w.avg_track_temp_c,
    w.avg_humidity_pct,
    w.avg_wind_speed,
    w.rain_detected

from lap_metrics l

left join results r

    on l.season = r.season
   and l.event_slug = r.event_slug
   and l.session_type = r.session_type
   and l.driver_code = r.driver_code

left join weather w

    on l.season = w.season
   and l.event_slug = w.event_slug
   and l.session_type = w.session_type