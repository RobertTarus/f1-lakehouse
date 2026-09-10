
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select season
from "iceberg"."bronze"."weather"
where season is null



  
  
      
    ) dbt_internal_test