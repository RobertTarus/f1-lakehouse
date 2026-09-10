
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select session_type
from "iceberg"."silver"."silver_results"
where session_type is null



  
  
      
    ) dbt_internal_test