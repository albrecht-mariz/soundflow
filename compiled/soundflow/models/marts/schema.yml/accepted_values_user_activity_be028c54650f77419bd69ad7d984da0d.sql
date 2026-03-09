
    
    

with all_values as (

    select
        subscription_type as value_field,
        count(*) as n_records

    from "soundflow"."marts"."user_activity"
    group by subscription_type

)

select *
from all_values
where value_field not in (
    'free','premium','family','student'
)


