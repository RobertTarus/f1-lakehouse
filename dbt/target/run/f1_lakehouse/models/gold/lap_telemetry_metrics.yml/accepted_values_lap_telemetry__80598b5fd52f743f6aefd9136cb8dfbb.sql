
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with all_values as (

    select
        has_lap_timing as value_field,
        count(*) as n_records

    from "iceberg"."gold"."lap_telemetry_metrics"
    group by has_lap_timing

)

select *
from all_values
where value_field not in (
    True,False
)



  
  
      
    ) dbt_internal_test