WITH source AS (
    SELECT * FROM {{ source('raw', 'users') }}
),

renamed AS (
    SELECT
        user_id,
        username,
        email,
        country,
        subscription_type,
        age_group,
        CAST(joined_at AS DATE)          AS joined_date,
        CAST(popularity_rank AS INTEGER) AS popularity_rank
    FROM source
)

SELECT * FROM renamed
