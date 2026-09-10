
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select sample_timestamp_utc
from "iceberg"."bronze"."telemetry"
where sample_timestamp_utc is null



  
  
      
    ) dbt_internal_test