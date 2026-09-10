
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select valid_laps
from "iceberg"."gold"."race_driver_performance"
where valid_laps is null



  
  
      
    ) dbt_internal_test