
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select platform
from "soundflow"."dev_staging"."stg_stream_events"
where platform is null



  
  
      
    ) dbt_internal_test