
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  -- Daily rank must be between 1 and 100 (top_tracks_daily is filtered to top 100).
-- Returns failing rows — zero rows = test passes.

SELECT *
FROM "soundflow"."marts"."top_tracks_daily"
WHERE
    daily_rank < 1
    OR daily_rank > 100
  
  
      
    ) dbt_internal_test