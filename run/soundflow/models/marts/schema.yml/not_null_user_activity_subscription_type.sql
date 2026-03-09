
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select subscription_type
from "soundflow"."dev_marts"."user_activity"
where subscription_type is null



  
  
      
    ) dbt_internal_test