
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select season
from "iceberg"."gold"."race_driver_performance"
where season is null



  
  
      
    ) dbt_internal_test