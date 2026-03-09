
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select artist_id
from "soundflow"."intermediate"."int_enriched_events"
where artist_id is null



  
  
      
    ) dbt_internal_test