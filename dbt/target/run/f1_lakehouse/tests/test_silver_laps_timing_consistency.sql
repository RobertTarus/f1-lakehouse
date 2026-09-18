
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  -- ============================================================
-- SILVER LAP TIMING CONSISTENCY
--
-- A lap can legitimately exist without an official lap time.
--
-- Rules:
--
-- has_lap_time = true
--     -> lap_time_ms must exist and be > 0
--
-- has_lap_time = false
--     -> lap_time_ms must be null or <= 0
--
-- dbt singular tests PASS when this query returns zero rows.
-- ============================================================

select
    season,
    event_slug,
    session_type,
    driver_code,
    lap_number,
    lap_time_ms,
    has_lap_time,
    lap_quality_status

from "iceberg"."silver"."silver_laps"

where
    (
        has_lap_time = true
        and (
            lap_time_ms is null
            or lap_time_ms <= 0
        )
    )

    or

    (
        has_lap_time = false
        and lap_time_ms is not null
        and lap_time_ms > 0
    )
  
  
      
    ) dbt_internal_test