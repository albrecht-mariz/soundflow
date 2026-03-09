
  
  create view "soundflow"."dev_staging"."stg_artists__dbt_tmp" as (
    WITH source AS (
    SELECT * FROM "soundflow"."raw"."artists"
),

renamed AS (
    SELECT
        artist_id,
        name                                AS artist_name,
        genre,
        country,
        CAST(monthly_listeners AS INTEGER)  AS monthly_listeners,
        CAST(created_at AS DATE)            AS created_date,
        CAST(popularity_rank AS INTEGER)    AS popularity_rank
    FROM source
)

SELECT * FROM renamed
  );
