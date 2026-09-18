
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  -- ============================================================
-- GOLD TELEMETRY LAP RECONCILIATION
--
-- Every telemetry lap must correspond to a Silver lap record.
-- ============================================================

select

    season,
    event_slug,
    session_type,
    driver_code,
    lap_number,
    lap_match_status

from "iceberg"."gold"."lap_telemetry_metrics"

where has_lap_record = false
   or lap_match_status = 'NO_LAP_RECORD'
  
  
      
    ) dbt_internal_test