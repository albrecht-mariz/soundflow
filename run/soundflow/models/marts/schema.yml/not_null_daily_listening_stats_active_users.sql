
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select active_users
from "soundflow"."marts"."daily_listening_stats"
where active_users is null



  
  
      
    ) dbt_internal_test