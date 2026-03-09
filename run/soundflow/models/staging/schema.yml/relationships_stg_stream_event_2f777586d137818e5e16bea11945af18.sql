
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with child as (
    select track_id as from_field
    from "soundflow"."dev_staging"."stg_stream_events"
    where track_id is not null
),

parent as (
    select track_id as to_field
    from "soundflow"."dev_staging"."stg_tracks"
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null



  
  
      
    ) dbt_internal_test