
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select username
from "soundflow"."staging"."stg_users"
where username is null



  
  
      
    ) dbt_internal_test