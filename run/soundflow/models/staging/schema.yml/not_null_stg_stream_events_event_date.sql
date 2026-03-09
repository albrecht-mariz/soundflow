
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select event_date
from "soundflow"."staging"."stg_stream_events"
where event_date is null



  
  
      
    ) dbt_internal_test