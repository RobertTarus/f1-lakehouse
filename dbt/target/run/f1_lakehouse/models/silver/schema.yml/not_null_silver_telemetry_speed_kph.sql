
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select speed_kph
from "iceberg"."silver"."silver_telemetry"
where speed_kph is null



  
  
      
    ) dbt_internal_test