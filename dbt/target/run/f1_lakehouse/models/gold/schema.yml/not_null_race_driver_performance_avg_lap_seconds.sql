
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select avg_lap_seconds
from "iceberg"."gold"."race_driver_performance"
where avg_lap_seconds is null



  
  
      
    ) dbt_internal_test