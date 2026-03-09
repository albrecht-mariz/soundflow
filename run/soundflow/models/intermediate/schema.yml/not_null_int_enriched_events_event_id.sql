
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select event_id
from "soundflow"."dev_intermediate"."int_enriched_events"
where event_id is null



  
  
      
    ) dbt_internal_test