
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select season
from "iceberg"."silver"."silver_laps"
where season is null



  
  
      
    ) dbt_internal_test