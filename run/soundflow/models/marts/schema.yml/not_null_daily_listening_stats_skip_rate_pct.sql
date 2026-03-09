
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select skip_rate_pct
from "soundflow"."dev_marts"."daily_listening_stats"
where skip_rate_pct is null



  
  
      
    ) dbt_internal_test