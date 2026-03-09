
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select daily_rank
from "soundflow"."marts"."top_tracks_daily"
where daily_rank is null



  
  
      
    ) dbt_internal_test