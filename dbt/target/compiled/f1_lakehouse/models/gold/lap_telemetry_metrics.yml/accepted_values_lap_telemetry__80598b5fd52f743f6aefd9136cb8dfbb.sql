
    
    

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


