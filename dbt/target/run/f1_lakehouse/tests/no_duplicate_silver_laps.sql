
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  select
    season,
    event_slug,
    session_type,
    driver_code,
    lap_number,
    count(*) as record_count

from "iceberg"."silver"."silver_laps"

group by
    season,
    event_slug,
    session_type,
    driver_code,
    lap_number

having count(*) > 1
  
  
      
    ) dbt_internal_test