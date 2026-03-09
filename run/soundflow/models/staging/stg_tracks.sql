
  
  create view "soundflow"."staging"."stg_tracks__dbt_tmp" as (
    WITH source AS (
    SELECT * FROM "soundflow"."raw"."tracks"
),

renamed AS (
    SELECT
        track_id,
        title                                           AS track_title,
        artist_id,
        album_id,
        CAST(duration_ms AS INTEGER)                    AS duration_ms,
        ROUND(CAST(duration_ms AS DOUBLE) / 1000.0, 1) AS duration_seconds,
        genre,
        CAST(release_year AS INTEGER)                   AS release_year,
        CAST(explicit AS BOOLEAN)                       AS is_explicit,
        CAST(tempo_bpm AS INTEGER)                      AS tempo_bpm,
        CAST(energy_score AS DOUBLE)                    AS energy_score,
        CAST(popularity_rank AS INTEGER)                AS popularity_rank
    FROM source
)

SELECT * FROM renamed
  );
