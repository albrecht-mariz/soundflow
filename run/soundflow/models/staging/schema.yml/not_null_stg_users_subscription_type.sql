
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select subscription_type
from "soundflow"."staging"."stg_users"
where subscription_type is null



  
  
      
    ) dbt_internal_test