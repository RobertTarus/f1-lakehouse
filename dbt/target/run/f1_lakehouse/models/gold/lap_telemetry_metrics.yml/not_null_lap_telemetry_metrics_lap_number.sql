
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select lap_number
from "iceberg"."gold"."lap_telemetry_metrics"
where lap_number is null



  
  
      
    ) dbt_internal_test