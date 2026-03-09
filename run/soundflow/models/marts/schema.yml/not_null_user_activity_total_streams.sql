
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select total_streams
from "soundflow"."marts"."user_activity"
where total_streams is null



  
  
      
    ) dbt_internal_test