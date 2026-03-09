
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select ms_played
from "soundflow"."intermediate"."int_enriched_events"
where ms_played is null



  
  
      
    ) dbt_internal_test