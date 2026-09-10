
    
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
    count(*) as record_count

from "iceberg"."gold"."race_driver_performance"

group by
    season,
    event_slug,
    session_type,
    driver_code

having count(*) > 1
  
  
      
    ) dbt_internal_test