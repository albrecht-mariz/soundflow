
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select genre
from "soundflow"."dev_marts"."genre_trends"
where genre is null



  
  
      
    ) dbt_internal_test