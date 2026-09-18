
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select driver_code
from "iceberg"."gold"."lap_telemetry_metrics"
where driver_code is null



  
  
      
    ) dbt_internal_test