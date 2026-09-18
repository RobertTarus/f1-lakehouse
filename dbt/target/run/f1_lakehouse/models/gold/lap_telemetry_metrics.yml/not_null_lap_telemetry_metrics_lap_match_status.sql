
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select lap_match_status
from "iceberg"."gold"."lap_telemetry_metrics"
where lap_match_status is null



  
  
      
    ) dbt_internal_test