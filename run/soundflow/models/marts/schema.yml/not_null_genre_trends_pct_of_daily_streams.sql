
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select pct_of_daily_streams
from "soundflow"."marts"."genre_trends"
where pct_of_daily_streams is null



  
  
      
    ) dbt_internal_test