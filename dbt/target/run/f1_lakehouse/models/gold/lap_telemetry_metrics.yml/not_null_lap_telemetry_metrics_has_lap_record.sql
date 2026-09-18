
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select has_lap_record
from "iceberg"."gold"."lap_telemetry_metrics"
where has_lap_record is null



  
  
      
    ) dbt_internal_test