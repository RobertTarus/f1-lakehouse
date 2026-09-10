
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select position
from "iceberg"."silver"."silver_results"
where position is null



  
  
      
    ) dbt_internal_test