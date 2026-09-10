select
    season,
    event_slug,
    session_type,
    driver_code,
    count(*) as record_count

from "iceberg"."gold"."race_driver_performance"

group by
    season,
    event_slug,
    session_type,
    driver_code

having count(*) > 1