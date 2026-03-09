
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select stream_count
from "soundflow"."dev_marts"."genre_trends"
where stream_count is null



  
  
      
    ) dbt_internal_test