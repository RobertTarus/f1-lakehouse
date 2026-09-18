
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
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

from "iceberg"."gold"."lap_telemetry_metrics"

group by

    season,
    event_slug,
    session_type,
    driver_code,
    lap_number

having count(*) > 1
  
  
      
    ) dbt_internal_test