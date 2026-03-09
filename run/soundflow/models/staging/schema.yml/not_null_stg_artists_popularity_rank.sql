
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select popularity_rank
from "soundflow"."staging"."stg_artists"
where popularity_rank is null



  
  
      
    ) dbt_internal_test