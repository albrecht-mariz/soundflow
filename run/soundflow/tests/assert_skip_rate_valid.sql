
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  -- Skip rate must be between 0 and 100.
-- Returns failing rows — zero rows = test passes.

SELECT *
FROM "soundflow"."marts"."daily_listening_stats"
WHERE
    skip_rate_pct < 0
    OR skip_rate_pct > 100
  
  
      
    ) dbt_internal_test