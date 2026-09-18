-- ============================================================
-- GOLD TELEMETRY UNIQUE GRAIN
--
-- Expected grain:
--
--     season
--     event_slug
--     session_type
--     driver_code
--     lap_number
--
-- dbt singular tests PASS when zero rows are returned.
-- ============================================================

select

    season,
    event_slug,
    session_type,
    driver_code,
    lap_number,

    count(*) as record_count

from {{ ref('lap_telemetry_metrics') }}

group by

    season,
    event_slug,
    session_type,
    driver_code,
    lap_number

having count(*) > 1
