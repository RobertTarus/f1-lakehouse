select
    season,
    event_slug,
    session_type,
    driver_code,
    lap_number,
    count(*) as record_count

from {{ ref('silver_laps') }}

group by
    season,
    event_slug,
    session_type,
    driver_code,
    lap_number

having count(*) > 1
