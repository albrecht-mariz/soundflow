
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select track_title
from "soundflow"."dev_staging"."stg_tracks"
where track_title is null



  
  
      
    ) dbt_internal_test