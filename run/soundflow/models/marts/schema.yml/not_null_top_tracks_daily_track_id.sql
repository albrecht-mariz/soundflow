
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select track_id
from "soundflow"."dev_marts"."top_tracks_daily"
where track_id is null



  
  
      
    ) dbt_internal_test