
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  -- The sum of pct_of_daily_streams per day must be ~100 (within rounding tolerance).
-- Returns failing days — zero rows = test passes.

SELECT
    event_date,
    ROUND(SUM(pct_of_daily_streams), 0) AS total_pct
FROM "soundflow"."marts"."genre_trends"
GROUP BY event_date
HAVING ROUND(SUM(pct_of_daily_streams), 0) NOT BETWEEN 99 AND 101
  
  
      
    ) dbt_internal_test