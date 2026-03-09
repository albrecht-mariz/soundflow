
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select started_at
from "soundflow"."raw"."stream_events"
where started_at is null



  
  
      
    ) dbt_internal_test