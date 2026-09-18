
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select has_lap_timing
from "iceberg"."gold"."lap_telemetry_metrics"
where has_lap_timing is null



  
  
      
    ) dbt_internal_test