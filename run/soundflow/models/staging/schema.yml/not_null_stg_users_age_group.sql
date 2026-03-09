
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select age_group
from "soundflow"."dev_staging"."stg_users"
where age_group is null



  
  
      
    ) dbt_internal_test