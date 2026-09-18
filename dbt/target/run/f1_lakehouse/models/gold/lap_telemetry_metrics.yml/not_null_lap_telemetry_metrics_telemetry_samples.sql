
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select telemetry_samples
from "iceberg"."gold"."lap_telemetry_metrics"
where telemetry_samples is null



  
  
      
    ) dbt_internal_test