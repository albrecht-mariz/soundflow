
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with all_values as (

    select
        device_type as value_field,
        count(*) as n_records

    from "soundflow"."staging"."stg_stream_events"
    group by device_type

)

select *
from all_values
where value_field not in (
    'mobile','desktop','tablet','tv','smart_speaker'
)



  
  
      
    ) dbt_internal_test