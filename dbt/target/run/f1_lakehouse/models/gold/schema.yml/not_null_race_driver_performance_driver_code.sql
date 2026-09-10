
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select driver_code
from "iceberg"."gold"."race_driver_performance"
where driver_code is null



  
  
      
    ) dbt_internal_test