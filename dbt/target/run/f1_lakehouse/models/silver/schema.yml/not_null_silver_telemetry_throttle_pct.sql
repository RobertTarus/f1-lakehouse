
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select throttle_pct
from "iceberg"."silver"."silver_telemetry"
where throttle_pct is null



  
  
      
    ) dbt_internal_test