
    
    

with all_values as (

    select
        lap_match_status as value_field,
        count(*) as n_records

    from "iceberg"."gold"."lap_telemetry_metrics"
    group by lap_match_status

)

select *
from all_values
where value_field not in (
    'MATCHED_WITH_LAP_TIME','MATCHED_NO_LAP_TIME','NO_LAP_RECORD'
)


