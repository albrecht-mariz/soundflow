# /build-dashboard

Build a Lightdash dashboard from a natural-language prompt.

Delegates to the `lightdash-agent` subagent, which will:
1. Show the available metrics and dimensions from `schema.yml`
2. Plan the dashboard tiles and wait for your approval
3. Create the draft dashboard in Lightdash via the REST API
4. Return the URL for review

## Usage

```
/build-dashboard show me weekly streams by genre over the last 90 days
/build-dashboard top 10 artists this week by completion rate
/build-dashboard daily active users and listening hours by subscription type
```

## Requirements

- Lightdash must be running: `docker-compose up lightdash-db lightdash`
- `.env` must have `LIGHTDASH_BASE_URL`, `LIGHTDASH_TOKEN`, `LIGHTDASH_PROJECT_UUID`
- Run `pip install -r bi_agent/requirements.txt` if not already installed

## After creation

The dashboard lands in the **"Draft — Pending Review"** space in Lightdash.
Open the URL, review the tiles, then move the dashboard to a shared space to publish.
Once published, update the `url:` field in `dbt_project/models/marts/exposures.yml`.
