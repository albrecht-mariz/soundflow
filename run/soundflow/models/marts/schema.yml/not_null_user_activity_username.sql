
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select username
from "soundflow"."dev_marts"."user_activity"
where username is null



  
  
      
    ) dbt_internal_test