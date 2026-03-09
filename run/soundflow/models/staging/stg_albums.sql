
  
  create view "soundflow"."dev_staging"."stg_albums__dbt_tmp" as (
    WITH source AS (
    SELECT * FROM "soundflow"."raw"."albums"
),

renamed AS (
    SELECT
        album_id,
        title                           AS album_title,
        artist_id,
        CAST(release_date AS DATE)      AS release_date,
        CAST(num_tracks AS INTEGER)     AS num_tracks,
        genre
    FROM source
)

SELECT * FROM renamed
  );
