# SKILLS.md — Agentic BI Roadmap

Phased plan for building the BI layer on top of the SoundFlow dbt marts, evolving from static dashboards to a fully agentic, Slack-native analytics experience.

---

## Do We Need a Semantic Layer?

**Short answer: yes, and Lightdash already provides one.**

Lightdash is built on top of dbt and acts as a semantic layer: you define metrics, dimensions, and joins once in YAML (inside your dbt `schema.yml` files), and every downstream consumer — dashboards, the Lightdash API, and later the Slack agent — queries through that same consistent layer.

For Phases 1–2, Lightdash's built-in semantic layer is sufficient. For Phase 3–4 (agent querying metrics programmatically), it is **strongly recommended** to also add [dbt Semantic Layer (MetricFlow)](https://docs.getdbt.com/docs/build/about-metricflow) on top of the marts. This exposes a standardized metrics API (JDBC/GraphQL) that agents can call without writing raw SQL, ensuring consistency regardless of which tool asks the question.

| Phase | Semantic Layer need |
|---|---|
| 1 — Static Lightdash | Lightdash YAML explores (implicit semantic layer) |
| 2 — Prompt → Dashboard | Same; agent generates Lightdash YAML |
| 3 — Slack agent (link or build) | Lightdash API + optional MetricFlow for metric lookup |
| 4 — Full in-Slack answers | dbt Semantic Layer (MetricFlow) strongly recommended |

---

## dbt Exposures for Dashboards

Exposures declare downstream uses of dbt models (dashboards, reports, ML models) inside the dbt project. They:
- Show up in `dbt docs` lineage as nodes downstream of marts.
- Prove which mart tables a dashboard depends on (useful for impact analysis).
- Are the standard way to link dbt to BI tools.

Create a dedicated `dbt_project/models/marts/exposures.yml`:

```yaml
version: 2

exposures:

  - name: platform_overview_dashboard
    type: dashboard
    maturity: high
    url: https://lightdash.example.com/dashboards/platform-overview
    description: >
      Daily platform KPIs: total streams, active users, completion rate,
      skip rate. Primary executive dashboard.
    depends_on:
      - ref('daily_listening_stats')
    owner:
      name: Data Team
      email: data@soundflow.io

  - name: top_tracks_dashboard
    type: dashboard
    maturity: high
    url: https://lightdash.example.com/dashboards/top-tracks
    description: >
      Daily top 100 tracks with stream counts, artist info, and rank movement.
    depends_on:
      - ref('top_tracks_daily')
    owner:
      name: Data Team
      email: data@soundflow.io

  - name: genre_trends_dashboard
    type: dashboard
    maturity: medium
    url: https://lightdash.example.com/dashboards/genre-trends
    description: >
      Genre popularity over time, share of daily streams, and rank trends.
    depends_on:
      - ref('genre_trends')
    owner:
      name: Data Team
      email: data@soundflow.io

  - name: user_segments_dashboard
    type: dashboard
    maturity: medium
    url: https://lightdash.example.com/dashboards/user-segments
    description: >
      All-time user listening behaviour, subscription type breakdown,
      and top-listener identification.
    depends_on:
      - ref('user_activity')
    owner:
      name: Data Team
      email: data@soundflow.io
```

---

## Phase 1 — Static Lightdash Dashboards

**Goal**: Lightdash running on top of the DuckDB dbt project. Four dashboards covering all marts.

### ⚠️ Lightdash Cloud vs Self-Hosted with DuckDB

| Option | DuckDB support | Notes |
|---|---|---|
| **Lightdash Cloud (free tier)** | ❌ Cannot access a local file | Would need [MotherDuck](https://motherduck.com/) (cloud DuckDB) as the warehouse |
| **Self-hosted Lightdash (open source, also free)** | ✅ Mount the DuckDB file directly | This is what the `docker-compose.yml` sets up |

**→ Use self-hosted** for this project. The `docker-compose.yml` already includes the Lightdash service (port 8090) and a Postgres sidecar for Lightdash's metadata store.

### Steps

1. **Lightdash connection** — already configured in `docker-compose.yml`:

    ```bash
    # Start Lightdash (standalone — do not run with pipeline simultaneously)
    docker-compose up lightdash-db lightdash

    # Open browser
    open http://localhost:8090
    ```

    On first launch, create an admin account, then connect the project by pointing
    Lightdash to the mounted dbt directory (`/usr/app/dbt` inside the container).
    The DuckDB file is mounted at `/data/soundflow.duckdb` (read-only).

    > **Note**: DuckDB allows only one writer at a time. Do not run `make pipeline`
    > or `make dbt` while Lightdash is running against the same file. Stop Lightdash
    > first, run the pipeline, restart Lightdash.

2. **Lightdash explores** — ✅ done. All 4 mart models in
   `dbt_project/models/marts/schema.yml` now have full `meta:` blocks with:
   - `dimension:` definitions (type + label) for every column
   - `metrics:` definitions (type + label) for every measurable column

3. **Build dashboards**: Use the Lightdash UI to build the four dashboards listed in `exposures.yml`.
   Suggested tile layout per dashboard:

   | Dashboard | Suggested tiles |
   |---|---|
   | Platform Overview | Total Streams over time, Active Users, Completion Rate vs Skip Rate, Platform split (bar), Subscription split (pie) |
   | Top Tracks | Table: rank / track / artist / streams / completion rate; filtered to last 7 days |
   | Genre Trends | Stream share over time (stacked area), Genre rank table, Avg % played by genre |
   | User Segments | Subscription type distribution, Country map, Preferred platform breakdown, Top users table |

4. **Update `exposures.yml`**: Once dashboards exist in Lightdash, copy each dashboard
   URL into `dbt_project/models/marts/exposures.yml` (the `url:` fields are pre-stubbed).

### Deliverables
- [x] `schema.yml` updated with `meta:` explore blocks for all 4 marts
- [x] `exposures.yml` created at `dbt_project/models/marts/exposures.yml`
- [x] Lightdash service + Postgres added to `docker-compose.yml` (port 8090)
- [ ] Lightdash running locally — start when off corporate machine: `docker-compose up lightdash-db lightdash`
- [ ] 4 dashboards built in Lightdash UI
- [ ] Dashboard URLs filled in `exposures.yml`
- [ ] `make dbt-docs` shows exposure nodes in lineage (run after dashboards built)

---

## Phase 2 — Prompt-to-Dashboard

**Goal**: Given a natural language prompt, an agent generates and creates a Lightdash dashboard, which a human then reviews and publishes.

### Architecture

```
User prompt
    │
    ▼
Agent (Claude API)
    │  ─ interprets intent
    │  ─ identifies relevant dbt mart(s) + available metrics/dimensions
    │  ─ generates Lightdash API payload (tiles, filters, layout)
    ▼
Lightdash REST API
    │  POST /api/v1/dashboards
    ▼
Draft dashboard (unpublished / in review space)
    │
    ▼
Human review & publish
```

### Key components

- **Lightdash API**: Lightdash exposes a REST API for creating/updating dashboards, charts (saved queries), and spaces. Authenticate via API token.
- **Available context for the agent**: The agent needs to know which metrics and dimensions exist. Feed it the `schema.yml` `meta:` blocks (or a compiled metrics manifest from dbt) as context.
- **Approval flow**: New dashboards land in a `Draft` space or with `is_private: true`. A human promotes them to a shared space.

### Implementation sketch

```python
# bi_agent/prompt_to_dashboard.py

import anthropic
import httpx

LIGHTDASH_BASE = "https://lightdash.example.com/api/v1"
LIGHTDASH_TOKEN = "..."  # from env

def build_dashboard_from_prompt(prompt: str, metrics_context: str) -> dict:
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2048,
        system=f"""
You are a BI engineer. Given a user prompt and the available metrics/dimensions below,
produce a valid Lightdash dashboard JSON payload (tiles array, filters, layout).
Only use the metrics and dimensions listed. Return only JSON.

Available metrics and dimensions:
{metrics_context}
""",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text  # parse as JSON

def create_draft_dashboard(payload: dict) -> str:
    r = httpx.post(
        f"{LIGHTDASH_BASE}/dashboards",
        json=payload,
        headers={"Authorization": f"ApiKey {LIGHTDASH_TOKEN}"},
    )
    r.raise_for_status()
    return r.json()["results"]["dashboardUuid"]
```

### Deliverables
- [ ] `bi_agent/` folder with `prompt_to_dashboard.py`
- [ ] Metrics context loader (reads `schema.yml` meta blocks or dbt manifest)
- [ ] Draft dashboard space in Lightdash for review
- [ ] Simple CLI: `python bi_agent/prompt_to_dashboard.py "show me weekly streams by genre"`

---

## Phase 3 — Slack Agent (Check → Link or Build with Approval)

**Goal**: Users ask KPI questions in Slack. The agent either returns an existing dashboard link or proposes a new dashboard for review.

### Architecture

```
Slack message (KPI question)
    │
    ▼
Slack Bolt app (Python)
    │
    ▼
Intent classifier (Claude API)
    │  ─ extracts KPI intent
    │  ─ maps to known dashboard tags
    ▼
Lightdash API: GET /dashboards (search by name/tag)
    │
    ├─ found ──────────────────────────────────────────►  Reply: "Here's the link: [url]"
    │
    └─ not found ──► Agent generates dashboard payload
                          │
                          ▼
                     Lightdash API: POST /dashboards (draft)
                          │
                          ▼
                     Slack approval message (Block Kit)
                     [Approve] [Reject] buttons
                          │
                     Approved ──► Lightdash API: PATCH publish dashboard
                                      │
                                      ▼
                                 Reply: "Dashboard created: [url]"
```

### Key components

1. **Slack Bolt app** (`slack_bolt` Python SDK): listens for `app_mention` or DM events.
2. **Intent extraction**: Claude API parses the question → structured intent `{kpi: "streams", breakdown: "genre", timeframe: "last 7 days"}`.
3. **Dashboard lookup**: Checks Lightdash API for existing dashboards matching the intent (by name, tags, or a local index of `exposures.yml`).
4. **Approval workflow**: Uses Slack Block Kit interactive components (buttons) to request approval from a designated reviewer before publishing.
5. **Approval gating**: Only the reviewer (or a role-gated set of users) can approve a new dashboard — use Slack user ID checks.

### Deliverables
- [ ] `bi_agent/slack_bot.py` (Slack Bolt app)
- [ ] `bi_agent/intent.py` (Claude API intent classifier)
- [ ] `bi_agent/dashboard_lookup.py` (Lightdash API search + exposures index)
- [ ] Approval workflow with Slack Block Kit interactive buttons
- [ ] Environment variables: `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `LIGHTDASH_TOKEN`, `ANTHROPIC_API_KEY`
- [ ] Deployment: Docker container or AWS Lambda

---

## Phase 4 — Full In-Slack Answers (No Lightdash Required)

**Goal**: Users get data answers directly in Slack — no need to open a browser. Agent queries the data layer and returns formatted results.

### Architecture

```
Slack question
    │
    ▼
Agent (Claude API)
    │  ─ interprets question
    │  ─ determines whether to: query metric / return chart URL / summarise trend
    ▼
┌─────────────────────────────────┐
│  Option A: dbt Semantic Layer   │  MetricFlow JDBC/GraphQL API
│  Option B: DuckDB direct query  │  Connects to soundflow.duckdb
│  Option C: Lightdash API        │  Runs saved query, returns CSV
└─────────────────────────────────┘
    │
    ▼
Format response:
  ─ Text: "Last 7 days streams: 34,210 (+8.2% vs prior week)"
  ─ Table: Slack Block Kit section blocks
  ─ Chart: Render PNG via Matplotlib/Plotly, upload to Slack Files API
    │
    ▼
Slack reply (in-thread)
```

### Semantic Layer here: strongly recommended

At this phase, a proper semantic layer prevents the agent from writing ad-hoc SQL against raw tables. Options:

| Option | Pros | Cons |
|---|---|---|
| **dbt Semantic Layer (MetricFlow)** | Metrics defined once, queried consistently via API; dbt-native | Requires dbt Cloud or self-hosted dbt Semantic Layer server; DuckDB support is experimental |
| **Lightdash API** (run saved queries) | Already in stack; no new infra | Agent must know which saved query to call; less flexible for ad-hoc |
| **Direct DuckDB query** | Simple; no extra infra | Agent writes SQL — risk of inconsistency; bypasses semantic layer |

**Recommended path**: Start with the Lightdash API (Phase 4a), then add MetricFlow (Phase 4b) once usage patterns stabilise.

### Deliverables
- [ ] `bi_agent/answer.py` (data retrieval + formatting)
- [ ] DuckDB query executor with parameter binding (no SQL injection)
- [ ] Slack chart renderer (Matplotlib PNG → Slack Files API)
- [ ] Conversation memory (thread context so follow-up questions work)
- [ ] Rate limiting + error handling for Slack reply

---

## Summary: Semantic Layer by Phase

| Phase | What plays the semantic layer role |
|---|---|
| 1 — Static dashboards | Lightdash YAML explores (metrics in `schema.yml meta:`) |
| 2 — Prompt → Dashboard | Lightdash YAML (fed as context to the agent) |
| 3 — Slack → link or build | Lightdash API + `exposures.yml` as a dashboard index |
| 4 — Full in-Slack answers | dbt Semantic Layer (MetricFlow) or Lightdash API for queries |

The investment in proper `meta:` blocks in `schema.yml` (Phase 1) pays off for every subsequent phase — it is the foundation the agent uses to know what questions are answerable.
