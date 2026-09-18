
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select event_slug
from "iceberg"."gold"."lap_telemetry_metrics"
where event_slug is null



  
  
      
    ) dbt_internal_test