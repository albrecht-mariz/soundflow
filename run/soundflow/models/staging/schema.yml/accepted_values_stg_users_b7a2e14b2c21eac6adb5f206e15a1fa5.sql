
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with all_values as (

    select
        subscription_type as value_field,
        count(*) as n_records

    from "soundflow"."dev_staging"."stg_users"
    group by subscription_type

)

select *
from all_values
where value_field not in (
    'free','premium','family','student'
)



  
  
      
    ) dbt_internal_test