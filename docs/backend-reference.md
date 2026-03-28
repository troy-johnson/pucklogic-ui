# PuckLogic — Backend Reference

**Domain:** FastAPI backend (`apps/api/`)
**See also:** [pucklogic-architecture.md](pucklogic-architecture.md) for system overview

---

## 1. Project Structure

```
apps/api/
├── main.py                      # FastAPI app, CORS, router registration
├── core/
│   ├── config.py                # pydantic-settings (reads .env)
│   └── dependencies.py          # FastAPI Depends() helpers
├── models/
│   └── schemas.py               # All Pydantic request/response schemas
├── repositories/
│   ├── league_profiles.py       # LeagueProfileRepository (list, get, create)
│   ├── players.py               # PlayerRepository
│   ├── projections.py           # ProjectionRepository (get_by_season)
│   ├── rankings.py              # RankingsRepository (legacy — not used by pipeline)
│   ├── scoring_configs.py       # ScoringConfigRepository (list, get, create)
│   ├── sources.py               # SourceRepository (list, get_by_name)
│   └── subscriptions.py         # SubscriptionRepository
├── routers/
│   ├── exports.py               # POST /exports/generate — PDF/Excel streaming
│   ├── health.py                # GET /health
│   ├── league_profiles.py       # GET/POST /league-profiles (owner-scoped, VORP input)
│   ├── rankings.py              # POST /rankings/compute — projection aggregation pipeline
│   ├── scoring_configs.py       # GET/POST /scoring-configs (presets + custom)
│   ├── sources.py               # GET /sources
│   ├── stripe.py                # POST /stripe/create-checkout-session + /webhook
│   └── user_kits.py             # GET/POST/DELETE /user-kits (source-weight presets)
├── services/
│   ├── cache.py                 # CacheService — Upstash Redis, 6h TTL, SHA-256 keys, SCAN invalidation
│   ├── exports.py               # generate_excel(), generate_pdf() — new RankedPlayer shape
│   ├── projections.py           # aggregate_projections, compute_weighted_stats, apply_scoring_config, compute_vorp
│   ├── rankings.py              # Legacy rank-based pipeline (not used by /rankings/compute)
│   └── scoring_validation.py   # validate_scoring_config() — PPP/PPG/PPA + SHP/SHG/SHA mutual exclusion
├── scrapers/
│   ├── base.py                  # BaseScraper ABC — async _check_robots_txt, _get_with_retry
│   ├── base_projection.py       # BaseProjectionScraper ABC — projection sources → player_projections
│   ├── matching.py              # PlayerMatcher — exact → alias → rapidfuzz (threshold 85)
│   ├── nhl_com.py               # NhlComScraper → player_stats
│   ├── moneypuck.py             # MoneyPuckScraper → player_stats
│   ├── nst.py                   # NstScraper (BeautifulSoup) → player_stats
│   ├── platform_positions.py    # ESPN (auto), Yahoo (OAuth2), Fantrax (stub) → player_platform_positions
│   ├── schedule_scores.py       # NHL schedule API → schedule_scores (OFF_NIGHT_THRESHOLD=16)
│   └── projection/
│       ├── __init__.py          # Shared helpers: upsert_source, upsert_projection_row,
│       │                        #   fetch_players_and_aliases, log_unmatched,
│       │                        #   update_last_successful_scrape, apply_column_map
│       ├── hashtag_hockey.py    # HTML scraper; per-game rate × GP conversion
│       ├── daily_faceoff.py     # CSV paste/upload
│       ├── dobber.py            # CSV paste/upload (paywalled)
│       ├── apples_ginos.py      # CSV paste/upload
│       ├── lineup_experts.py    # CSV paste/upload
│       ├── yahoo.py             # Yahoo Fantasy API (OAuth2); paginated via game.player_stats()
│       └── fantrax.py           # Fantrax REST API; inherits BaseScraper
└── tests/
    ├── conftest.py              # client fixture (TestClient)
    ├── test_health.py
    ├── repositories/            # test_players, test_projections, test_sources,
    │                            #   test_league_profiles, test_scoring_configs, test_subscriptions
    ├── routers/                 # test_rankings, test_exports, test_sources,
    │                            #   test_league_profiles, test_scoring_configs,
    │                            #   test_stripe, test_user_kits
    ├── scrapers/                # test_base, test_base_projection, test_nhl_com, test_moneypuck,
    │                            #   test_platform_positions, test_schedule_scores
    │   └── projection/          # test_hashtag_hockey, test_daily_faceoff, test_dobber,
    │                            #   test_apples_ginos, test_lineup_experts, test_yahoo, test_fantrax
    └── services/                # test_projections, test_cache, test_exports,
                                 #   test_rankings (legacy), test_scoring_validation
```

---

## 2. Database Schema

### Full SQL DDL

```sql
-- Player identity
CREATE TABLE players (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nhl_id INTEGER UNIQUE,          -- NHL.com player ID (canonical key)
  name TEXT NOT NULL,
  team TEXT,
  position TEXT,                   -- C, LW, RW, D (skaters only at launch)
  date_of_birth DATE,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE player_aliases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  player_id UUID REFERENCES players(id),
  alias_name TEXT NOT NULL,
  source TEXT,                     -- which source uses this name variant
  UNIQUE(alias_name, source)
);

-- Rankings data
CREATE TABLE sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  url TEXT,
  scrape_config JSONB,
  active BOOLEAN DEFAULT true,
  last_successful_scrape TIMESTAMPTZ,
  default_weight FLOAT,            -- PuckLogic Recommended default weight (projection accuracy)
  is_paid BOOLEAN DEFAULT false,   -- true for paywalled/premium sources
  user_id UUID REFERENCES auth.users(id)  -- NULL for system sources; set for user-uploaded custom sources
);
-- Custom source privacy: GET /sources always filters to user_id IS NULL (system sources only).
--   Service-role key bypasses RLS so this filter is mandatory in the query.
-- 2-custom-source limit: count WHERE user_id = current_user.id AND active = TRUE; HTTP 400 if >= FREE_SLOT_LIMIT (2).
--   Post-upsert TOCTOU guard: re-count after insert and roll back + 400 if limit exceeded.

-- player_rankings: retained for potential future rank-only sources.
-- NOT read by POST /rankings/compute — the aggregation pipeline uses player_projections.
CREATE TABLE player_rankings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  player_id UUID REFERENCES players(id),
  source_id UUID REFERENCES sources(id),
  rank INTEGER,
  score FLOAT,
  season TEXT,                     -- e.g. "2026-27"
  scraped_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(player_id, source_id, season)
);

-- Staging table for atomic swap pattern (same schema as player_rankings)
CREATE TABLE player_rankings_staging (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  player_id UUID REFERENCES players(id),
  source_id UUID REFERENCES sources(id),
  rank INTEGER,
  score FLOAT,
  season TEXT,
  scraped_at TIMESTAMPTZ DEFAULT now()
);

-- Stats & ML
CREATE TABLE player_stats (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  player_id UUID REFERENCES players(id),
  season TEXT NOT NULL,
  gp INTEGER, g INTEGER, a INTEGER, pts INTEGER,
  ppp INTEGER,                     -- power play points
  toi_per_game FLOAT,             -- minutes
  sog INTEGER,                     -- shots on goal
  hits INTEGER, blocks INTEGER,
  hits_per60 FLOAT,               -- Marcel-weighted physical rate (from NST iHF/60)
  blocks_per60 FLOAT,             -- Marcel-weighted physical rate (from NST iBLK/60)
  cf_pct FLOAT,                   -- Corsi for %
  xgf_pct FLOAT,                  -- expected goals for %
  iscf_per_60 FLOAT,              -- individual scoring chances per 60 (KEY METRIC)
  sh_pct FLOAT,                   -- shooting %
  pdo FLOAT,
  war FLOAT,                      -- from Evolving Hockey
  UNIQUE(player_id, season)
);

CREATE TABLE player_trends (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  player_id UUID REFERENCES players(id),
  season TEXT NOT NULL,
  breakout_score FLOAT,           -- 0-1 probability
  regression_risk FLOAT,          -- 0-1 probability
  confidence FLOAT,               -- model confidence
  shap_values JSONB,              -- pre-computed SHAP explanations per feature
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(player_id, season)
);

-- player_projections: one row per player per source per season.
-- Written by projection source scrapers (BaseProjectionScraper subclasses) only.
-- NHL.com and MoneyPuck write to player_stats, not here.
-- NHL.com uses aggregate season rows (`isAggregate=true`) so traded players keep one combined season row.
-- null = source did not project this stat (displayed as —); 0 = projected at zero. Do not conflate.
-- PPP = PPG + PPA and SHP = SHG + SHA by definition; scoring_configs must not assign non-zero
-- weights to both PPP and PPG/PPA (or SHP and SHG/SHA) simultaneously — enforced at config creation.
CREATE TABLE player_projections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  player_id UUID REFERENCES players(id),
  source_id UUID REFERENCES sources(id),
  season TEXT NOT NULL,
  -- Skater stats (all nullable)
  g INTEGER, a INTEGER, plus_minus INTEGER, pim INTEGER,
  ppg INTEGER, ppa INTEGER, ppp INTEGER,
  shg INTEGER, sha INTEGER, shp INTEGER,
  sog INTEGER, fow INTEGER, fol INTEGER,
  hits INTEGER, blocks INTEGER, gp INTEGER,
  -- Goalie stats (all nullable)
  gs INTEGER, w INTEGER, l INTEGER, ga INTEGER,
  sa INTEGER, sv INTEGER, sv_pct FLOAT, so INTEGER, otl INTEGER,
  -- Overflow for source-specific stats not in the fixed set
  extra_stats JSONB,
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(player_id, source_id, season)
);

-- Schedule-based supplementary signal (not added to fantasy points)
-- "Off night" = calendar date where < 16 of 32 NHL teams play.
-- schedule_score: min-max normalized 0–1 across all players with GP > 0 for the season.
-- Recomputed in full whenever the NHL schedule changes.
CREATE TABLE schedule_scores (
  player_id UUID REFERENCES players(id),
  season TEXT NOT NULL,
  off_night_games INTEGER,        -- team games on nights where < 16 teams play
  total_games INTEGER,            -- projected GP for the season
  schedule_score FLOAT,           -- min-max normalized 0–1
  PRIMARY KEY (player_id, season)
);

-- Platform-specific position eligibility (separate from players.position which is NHL.com canonical)
CREATE TABLE player_platform_positions (
  player_id UUID REFERENCES players(id),
  platform TEXT NOT NULL,         -- 'espn', 'yahoo', 'fantrax'
  positions TEXT[] NOT NULL,      -- e.g. '{"LW","RW"}'
  PRIMARY KEY (player_id, platform)
);

-- User data (RLS-protected)
CREATE TABLE scoring_configs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  stat_weights JSONB NOT NULL,    -- {g: 3, a: 2, ppp: 1, sog: 0.5, ...}
  is_preset BOOLEAN DEFAULT false,
  user_id UUID REFERENCES auth.users(id),  -- NULL for presets
  created_at TIMESTAMPTZ DEFAULT now()
);

-- user_kits: named source-weight presets only. Does NOT store league config.
-- Full league configuration (platform, num_teams, roster_slots, scoring) lives in league_profiles.
CREATE TABLE user_kits (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id),  -- NULL for anonymous sessions
  session_token UUID,              -- for anonymous kit building
  name TEXT,
  source_weights JSONB NOT NULL,  -- {source_id: weight, ...}
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  CHECK (user_id IS NOT NULL OR session_token IS NOT NULL)
);

-- Complete league configuration for VORP computation.
-- Separate from user_kits (which are reusable source-weight presets).
CREATE TABLE league_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id),
  name TEXT NOT NULL,             -- e.g. "My ESPN H2H League"
  platform TEXT NOT NULL,         -- 'espn', 'yahoo', 'fantrax'
  num_teams INTEGER NOT NULL,
  roster_slots JSONB NOT NULL,    -- {"C":2,"LW":2,"RW":2,"D":4,"G":2,"UTIL":1,"BN":4}
  scoring_config_id UUID REFERENCES scoring_configs(id),
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE draft_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id),
  platform TEXT NOT NULL,          -- 'espn' or 'yahoo'
  league_config JSONB,
  picks JSONB DEFAULT '[]',
  available JSONB DEFAULT '[]',
  kit_id UUID REFERENCES user_kits(id),
  status TEXT DEFAULT 'active',    -- 'active', 'completed', 'expired'
  activated_at TIMESTAMPTZ DEFAULT now(),
  expires_at TIMESTAMPTZ
);

CREATE TABLE exports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id),
  type TEXT NOT NULL,              -- 'pdf', 'excel', 'bundle'
  status TEXT DEFAULT 'pending',   -- 'pending', 'generating', 'complete', 'failed'
  storage_url TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE subscriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id),
  stripe_session_id TEXT,
  plan TEXT,
  status TEXT DEFAULT 'active',
  expires_at TIMESTAMPTZ
);

-- Injury tracking — one row per player (upserted daily via NHL.com injury feed).
-- Feeds the Layer 2 "return from injury" signal in v2.0.
-- status values: 'healthy' | 'day-to-day' | 'week-to-week' | 'ir' | 'ltir'
CREATE TABLE injury_reports (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  player_id   UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  status      TEXT NOT NULL CHECK (status IN ('healthy', 'day-to-day', 'week-to-week', 'ir', 'ltir')),
  description TEXT,
  updated_at  TIMESTAMPTZ DEFAULT now(),
  UNIQUE (player_id)
);

-- Per-run audit trail written by every scraper on start/finish.
-- Powers the /admin/scraper-health dashboard.
CREATE TABLE scraper_logs (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  scraper_name   TEXT NOT NULL,
  status         TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed')),
  started_at     TIMESTAMPTZ DEFAULT now(),
  completed_at   TIMESTAMPTZ,
  rows_inserted  INTEGER,
  error_message  TEXT,
  traceback      TEXT
);

-- Daily line/unit assignments per player — EV, PP, and PK context.
-- One row per player per date (upserted by DailyFaceoff scraper).
-- Primary data source for Layer 2 line combo change signals.
-- Also supplies line quality features for Phase 3 ML training.
CREATE TABLE player_lines (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  player_id       UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  season          TEXT NOT NULL,
  date            DATE NOT NULL,
  -- Even strength
  ev_line         SMALLINT CHECK (ev_line BETWEEN 1 AND 4),  -- F: 1=top…4=4th; D: 1–3
  ev_toi_pg       NUMERIC(5,2),   -- EV TOI per game for this stretch
  ev_linemate_ids UUID[],         -- other skaters on this unit
  -- Power play
  pp_unit         SMALLINT CHECK (pp_unit BETWEEN 1 AND 2),  -- NULL = not on PP
  pp_toi_pg       NUMERIC(5,2),
  pp_linemate_ids UUID[],
  -- Penalty kill
  pk_unit         SMALLINT CHECK (pk_unit BETWEEN 1 AND 2),  -- NULL = not on PK
  pk_toi_pg       NUMERIC(5,2),
  pk_linemate_ids UUID[],
  source          TEXT NOT NULL,  -- e.g. 'dailyfaceoff'
  recorded_at     TIMESTAMPTZ DEFAULT now(),
  UNIQUE (player_id, date)
);
```

---

## 3. Security Model

The backend uses `SUPABASE_SERVICE_ROLE_KEY` (bypasses RLS). Security is enforced in two layers:

### RLS Policies (Supabase PostgreSQL)

```sql
-- Public read for player data (players, rankings, stats, trends, projections)
ALTER TABLE players ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read" ON players FOR SELECT USING (true);
-- (same pattern for player_rankings, player_stats, player_trends, player_projections, sources)

-- Preset scoring configs are public read
CREATE POLICY "Public preset read" ON scoring_configs
  FOR SELECT USING (is_preset = true);

-- Owner-only for user data
ALTER TABLE user_kits ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Owner or session" ON user_kits
  FOR ALL USING (
    auth.uid() = user_id
    OR session_token = current_setting('request.cookies')::jsonb->>'pucklogic_session'
  );

-- Service role only for writes to public tables
CREATE POLICY "Service write" ON player_rankings
  FOR INSERT WITH CHECK (auth.role() = 'service_role');
-- (same pattern for player_stats, player_trends, player_projections)
```

### API-Layer Ownership Checks

All user-owned data (user_kits, draft_sessions, exports, subscriptions, custom scoring_configs) requires explicit ownership assertions in every endpoint:

```python
# Pattern: check ownership before every operation on user data
async def get_kit(kit_id: str, current_user: User = Depends(get_current_user)):
    kit = await db.fetch_one(
        "SELECT * FROM user_kits WHERE id = :id", {"id": kit_id}
    )
    if not kit:
        raise HTTPException(404, "Kit not found")
    # ALWAYS check ownership
    if kit["user_id"] != current_user.id and kit["session_token"] != request.cookies.get("pucklogic_session"):
        raise HTTPException(403, "Forbidden")
    return kit
```

**Summary by table:**
| Table | Read | Write |
|-------|------|-------|
| players, player_rankings, player_stats, player_trends | Public (RLS) | Service role only |
| player_projections, schedule_scores, player_platform_positions | Public (RLS) | Service role only |
| sources (user_id IS NULL) | Public (RLS) | Service role only |
| sources (user_id IS NOT NULL) | Owner only (API filters) | Owner (API check) |
| scoring_configs (is_preset=true) | Public (RLS) | Service role only |
| user_kits | Owner or matching session_token | Owner (API check) |
| league_profiles | Owner (API check) | Owner (API check) |
| draft_sessions | Owner (API check) | Owner (API check) |
| exports | Owner (API check) | Owner (API check) |
| subscriptions | Owner (API check) | Stripe webhook (service role) |
| scoring_configs (custom) | Owner (API check) | Owner (API check) |

---

## 4. API Routes

### Implemented (Phase 2)

```
GET    /health                       — Health check

GET    /sources                      — List active system sources (user_id IS NULL; no auth required)
GET    /sources/custom               — List the authenticated user's custom sources (auth required)
                                       Returns: [{id, name, display_name, player_count, season, created_at}]
POST   /sources/upload               — Upload a CSV or Excel projection file as a custom source (auth required)
                                       Form: file (CSV/.xlsx, max 5 MB), source_name, season,
                                             column_map (JSON: {their_col: our_stat}),
                                             player_name_column? (defaults to first col not in column_map)
                                       Limits: 2 custom slots per user; TOCTOU guard post-upsert
                                       Paywalled gate: 403 if source_name matches a registered is_paid source
                                             and user has no active subscription
                                       Returns: {source_id, rows_upserted, unmatched[], slots_used, slots_total}
DELETE /sources/{id}                 — Delete a custom source (auth required, owner only)
                                       Cascades player_projections; invalidates cache per season

POST   /rankings/compute             — Projection aggregation pipeline (auth required)
                                       Body: { season, source_weights, scoring_config_id,
                                               platform, league_profile_id? }

GET    /scoring-configs/presets      — List preset scoring configs (public — no auth required)
GET    /scoring-configs              — List presets + user's custom configs (auth required)
POST   /scoring-configs              — Create custom scoring config (auth required)
                                       Validates: PPP+PPG/PPA and SHP+SHG/SHA mutual exclusion → HTTP 400

GET    /league-profiles              — List user's league profiles (auth required)
POST   /league-profiles              — Create league profile (auth required)
                                       platform: espn | yahoo | fantrax

GET    /user-kits                    — List user's source-weight presets (auth required)
POST   /user-kits                    — Create source-weight preset (auth required)
DELETE /user-kits/{id}               — Delete preset (auth required, owner only)

POST   /exports/generate             — Run pipeline and stream PDF or Excel (auth required)
                                       Body: same as /rankings/compute + export_type: pdf|excel
                                       Returns streaming bytes (Content-Disposition: attachment)

POST   /stripe/create-checkout-session  — Stripe checkout (auth required)
POST   /stripe/webhook               — Stripe webhook (signature-verified)

POST   /auth/register                — Supabase sign_up; returns {access_token, refresh_token, user}
                                       202 if email confirmation required; 400 on duplicate email
POST   /auth/login                   — Supabase sign_in_with_password; returns same shape
POST   /auth/logout                  — Revokes session via admin.sign_out(jwt); returns 204 (auth required)
POST   /auth/refresh                 — Exchanges refresh_token for new tokens
GET    /auth/me                      — Returns {id, email} for the authenticated user (auth required)

GET    /players                      — Paginated player list (?limit=100&offset=0, max limit 500)
GET    /players/{id}                 — Single player by UUID; 404 if not found
```

### Planned (Phase 3+, not yet implemented)

```
GET    /players/{id}/trends          — Breakout/regression scores + SHAP

GET    /trends/breakouts             — Top breakout candidates
GET    /trends/regressions           — Regression watchlist

POST   /draft/session                — Create draft session (subscription required)
WS     /ws/draft/{session_id}        — Live draft WebSocket
```

### Auth Middleware Pattern

`get_current_user` lives in `core/dependencies.py` and is injected via `Depends()`:

```python
# core/dependencies.py
async def get_current_user(authorization: str | None = Header(None)) -> dict[str, Any]:
    token = authorization.removeprefix("Bearer ")
    response = get_db().auth.get_user(token)
    return {"id": response.user.id, "email": response.user.email, "token": token}
    # raises HTTP 401 on missing header, invalid token, or expired token
```

The returned dict includes `"token"` (the raw JWT) so that logout can call `admin.sign_out(user["token"])` server-side.

---

## 5. Aggregation Pipeline (POST /rankings/compute)

The pipeline is **stat-projection-based**, not rank-based. Sources publish projected counting stats; the pipeline aggregates them to fantasy points and VORP.

```python
# services/projections.py

def compute_weighted_stats(
    player_rows: list[ProjectionRow],
    source_weights: dict[str, float],
) -> dict[str, float | None]:
    """
    For each stat: SUM(stat × weight) / SUM(weights for sources that have this stat).
    Nulls are excluded per-stat — a source projecting goals but not hits contributes
    to the goals average only.
    Returns null for a stat only if no source projected it.
    """
    ...

def apply_scoring_config(stats: dict, scoring_config: dict) -> float:
    """
    projected_stats: {g: 30, a: 45, ppp: 20, sog: 250, hits: 100, ...}
    scoring_config.stat_weights: {g: 3, a: 2, ppp: 1, sog: 0.5, hits: 0.5, ...}
    Null stats contribute 0. Keys must match player_projections column names.
    PPP/PPG/PPA and SHP/SHG/SHA mutual exclusion validated at config creation (HTTP 400).
    """
    return sum(
        (stats.get(stat) or 0) * weight
        for stat, weight in scoring_config["stat_weights"].items()
    )

def compute_vorp(
    players: list[AggregatedPlayer],
    league_profile: LeagueProfile,
) -> dict[str, float | None]:
    """
    Position group = players.position (NHL.com canonical).
    Replacement level = Nth player where N = (num_teams × position_slots) + 1.
    If fewer than N players at a position, use the last available as replacement level.
    If zero players at a position, vorp = null for all in that group.
    Negative VORP allowed — do not clamp at 0.
    If player has null projected_fantasy_points, vorp = null.
    """
    ...
```

**Request shape:**
```json
{
  "season": "2025-26",
  "source_weights": {"hashtag_hockey": 10, "apples_ginos": 5, "dobber": 8},
  "scoring_config_id": "uuid",
  "platform": "yahoo",
  "league_profile_id": "uuid"   // optional; omit to skip VORP
}
```

**Response per player** includes: `composite_rank`, `player_id`, `name`, `team`, `default_position`, `platform_positions`, `projected_fantasy_points`, `vorp`, `schedule_score`, `off_night_games`, `source_count`, `projected_stats` (full stat object, null for unprojected stats).

**Caching:** Results cached in Upstash Redis for 6h. Cache key: `rankings:{season}:{sha256(source_weights_sorted + scoring_config_id + platform + league_profile_id)}`. Cache invalidated on every new source ingest via `invalidate_rankings(season)` which pattern-deletes `rankings:{season}:*`.

---

## 6. Scraper Patterns

### Two scraper ABCs

**`BaseScraper`** — for stat sources (NHL.com, MoneyPuck, Natural Stat Trick). Writes to `player_stats`. Also mixed into projection scrapers that need HTTP (Yahoo, Fantrax) to get `_check_robots_txt` and `_get_with_retry`.

```python
from abc import ABC

class BaseScraper(ABC):
    async def _check_robots_txt(self, base_url: str) -> bool:
        """Fetch and parse robots.txt; return True if scraping is allowed."""
        ...

    async def _get_with_retry(self, url: str, **kwargs) -> httpx.Response:
        """GET with exponential backoff; raises on persistent failure."""
        ...
```

Projection scrapers that make HTTP requests (Yahoo, Fantrax) inherit `(BaseScraper, BaseProjectionScraper)` to get both the robots.txt check and the retry-capable HTTP client. CSV-only projection scrapers (DailyFaceoff, Dobber, etc.) inherit `BaseProjectionScraper` only.

**`BaseProjectionScraper`** — for projection sources (HashtagHockey, DailyFaceoff, etc. and user-uploaded custom sources). Writes to `player_projections`.

```python
class BaseProjectionScraper(ABC):
    SOURCE_NAME: str   # matches sources.name
    DISPLAY_NAME: str

    @abstractmethod
    async def scrape(self, season: str, db: Client) -> int:
        """Fetch projections, resolve player names, write to player_projections.
        Returns count of rows upserted."""
        ...
```

Name resolution: at ingest time, every source player name is fuzzy-matched against `players.name` (NHL.com canonical) using `scrapers/matching.py` (rapidfuzz). Confidence ≥ threshold → write row with resolved `player_id`. Confidence < threshold → log to `scraper_logs` with unmatched name, skip row. After each ingest job, surface summary to dashboard (e.g. "847 matched, 12 unmatched"). No silent drops.

### GitHub Actions Cron

Two workflows:

**Daily stat refresh** (NHL.com, MoneyPuck, NST → `player_stats`):
```yaml
# .github/workflows/daily-scrape.yml
name: Daily Data Refresh
on:
  schedule:
    - cron: '0 6 * * *'   # 6 AM UTC daily
  workflow_dispatch:        # manual trigger

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -r apps/api/requirements.txt
      - run: python -m apps.api.scrapers.nhl_com        # → player_stats
      - run: python -m apps.api.scrapers.moneypuck       # → player_stats
      - run: python -m apps.api.scrapers.nst             # → player_stats
    - if: failure()
      uses: slackapi/slack-github-action@v1
      with:
        webhook: ${{ secrets.SLACK_WEBHOOK }}
```

**Pre-season projection scrape** (HashtagHockey, DailyFaceoff, etc. → `player_projections`):
Each projection scraper runs pre-season (Monday 6am UTC weekly); triggers `invalidate_rankings(season)` on completion.
Workflow: `.github/workflows/scrape-projections.yml`

**Pre-season platform data** (positions + schedule → `player_platform_positions`, `schedule_scores`):
Runs once annually on Sep 1 8am UTC (before the season starts). Safe to re-run — all writes use UPSERT.
Workflow: `.github/workflows/scrape-platform-data.yml`
- ESPN position eligibility (auto-scrape, exponential-backoff retry)
- Yahoo position eligibility (OAuth2 — requires `YAHOO_OAUTH_REFRESH_TOKEN`)
- Schedule scores: NHL schedule API → off-night game counts, normalized to 0–1 (`OFF_NIGHT_THRESHOLD=16` teams = ≤8 games)

### Scraper Failure Handling

- Stat scrapers write via upsert to `player_stats`; projection scrapers upsert to `player_projections`
- Any failure → log error to `scraper_logs`, serve stale data with "last updated X hours ago" badge
- After each ingest, surface unmatched player name summary to dashboard
- GitHub Actions sends Slack/email alert on failure

---

### Scraper Smoke Test Runbook

Run this after any scraper change to verify data actually lands in Supabase.

**Prerequisites**

```bash
cd apps/api
cp .env.example .env          # if not already present
# Set in .env:
#   SUPABASE_URL=https://<project>.supabase.co
#   SUPABASE_SERVICE_ROLE_KEY=<service_role_key>
#   CURRENT_SEASON=2025-26

pip install -e ".[dev]"
```

> Target the **dev** Supabase project, not production. All writes are upserts so re-running is safe.

---

#### NHL.com

```bash
python -m scrapers.nhl_com
# Expected output: "Upserted N summary rows, M realtime rows."
```

Implementation notes:
- NHL.com summary and realtime endpoints must use `isAggregate=true` so traded players are returned as one combined season row.
- When `teamAbbrevs` is comma-joined (for example `"TOR,BUF"`), store only the last/current team in `players.team`.
- Realtime pass resolves players from the summary map first, then falls back to `players.nhl_id` lookup before skipping.

Verify in Supabase SQL editor:

```sql
-- Rankings written
SELECT COUNT(*) FROM player_rankings pr
JOIN sources s ON s.id = pr.source_id
WHERE s.name = 'nhl_com' AND pr.season = '2025-26';
-- Expect: > 500 rows

-- player_stats written from summary pass (gp, g, a)
SELECT p.name, ps.gp, ps.g, ps.a
FROM player_stats ps
JOIN players p ON p.id = ps.player_id
WHERE ps.season = '2025-26'
  AND ps.gp IS NOT NULL
ORDER BY ps.g DESC NULLS LAST
LIMIT 10;
-- Expect: top scorers with non-null gp, g, a

-- player_stats written from realtime pass (hits, blocks)
SELECT p.name, ps.hits, ps.blocks
FROM player_stats ps
JOIN players p ON p.id = ps.player_id
WHERE ps.season = '2025-26'
  AND (ps.hits IS NOT NULL OR ps.blocks IS NOT NULL)
ORDER BY ps.hits DESC NULLS LAST, ps.blocks DESC NULLS LAST
LIMIT 10;
-- Expect: non-null hits/blocks for physical-volume leaders
```

**Pass criteria:** `player_rankings` has ≥ 500 rows; summary-driven `player_stats` rows show non-null `gp`, `g`, `a`; realtime-driven rows show non-null `hits`/`blocks` for known leaders.

#### Natural Stat Trick (NST)

Implementation notes:
- NST header labels have changed over time; parser support must handle both legacy and current names for hits/blocks per-60.
- Current live NST pages may expose `Hits/60` and `Shots Blocked/60` where older fixtures/pages used `iHF/60` and `iBLK/60`.
- Situation pages may expose explicit `TOI/GP`; prefer that when present rather than deriving from total `TOI`.
- `toi_sh` should represent short-handed TOI per game, not all-situations TOI per game.

---

#### MoneyPuck

```bash
python -m scrapers.moneypuck
# Expected output: "MoneyPuck: upserted N rankings for 2025-26"
```

Verify:

```sql
-- player_stats written (ixg_per60, g_minus_ixg, xgf_pct_5v5)
SELECT p.name, ps.ixg_per60, ps.g_minus_ixg, ps.xgf_pct_5v5
FROM player_stats ps
JOIN players p ON p.id = ps.player_id
WHERE ps.season = '2025-26'
  AND ps.ixg_per60 IS NOT NULL
ORDER BY ps.ixg_per60 DESC NULLS LAST
LIMIT 10;
-- Expect: top players with non-null ixg_per60, g_minus_ixg
-- xgf_pct_5v5 may be null for players with zero 5v5 on-ice xG

-- Sanity check arithmetic (Connor McDavid, id varies)
SELECT p.name, ps.ixg_per60, ps.g_minus_ixg, ps.xgf_pct_5v5
FROM player_stats ps
JOIN players p ON p.id = ps.player_id
WHERE p.name ILIKE '%mcdavid%' AND ps.season = '2025-26';
-- ixg_per60 should be a positive float (~3–5 range for elite players)
-- g_minus_ixg positive = lucky shooter, negative = unlucky
-- xgf_pct_5v5 should be 50–70 range for top players
```

**Pass criteria:** At least 400 `player_stats` rows with non-null `ixg_per60`; `xgf_pct_5v5` populated for players with 5v5 ice time.

---

#### Natural Stat Trick (NST)

```bash
python -m scrapers.nst
# Expected output: "NstScraper: upserted N/M player_stats rows for 2025-26"
# N < M is normal — some names won't resolve on first run if players table is sparse
```

Verify:

```sql
-- Phase 3 Tier 1 columns written
SELECT p.name,
       ps.cf_pct, ps.xgf_pct, ps.sh_pct, ps.pdo,
       ps.icf_per60, ps.ixg_per60, ps.scf_pct, ps.scf_per60, ps.p1_per60,
       ps.xgf_pct_5v5, ps.toi_ev, ps.toi_pp, ps.toi_sh
FROM player_stats ps
JOIN players p ON p.id = ps.player_id
WHERE ps.season = '2025-26'
  AND ps.cf_pct IS NOT NULL
ORDER BY ps.icf_per60 DESC NULLS LAST
LIMIT 10;
-- Expect: rows with a mix of the above columns populated

-- Check unmatched names (expected to be low after NHL.com has run first)
SELECT COUNT(*) FROM scraper_logs
WHERE scraper_name = 'nst'
  AND event = 'unmatched_player'
  AND created_at > NOW() - INTERVAL '1 hour';
-- Expect: < 20 unmatched for a healthy run
```

**Pass criteria:** At least 300 `player_stats` rows with non-null `cf_pct`; all 9 all-situations columns and 4 situation columns (`xgf_pct_5v5`, `toi_ev`, `toi_pp`, `toi_sh`) present for the top rows.

> **Note:** Run NHL.com first. NST matches by player name against the `players` table; an empty `players` table means 0 matches.

---

#### Hockey Reference (`scrapers/hockey_reference.py`)

- **Table:** `player_stats`
- **Columns:** `sh_pct_career_avg` (float, rolling career SH%), `nhl_experience` (int, seasons with GP>0), `career_goals` (int), `career_shots` (int)
- **Frequency:** Annual (retraining cron) — `scrape_history("2005-06", current_season, db)` for initial backfill; `scrape(season, db)` for yearly updates
- **Rate limit:** `Crawl-delay: 3` per robots.txt — `MIN_DELAY_SECONDS = 3.0`

#### Elite Prospects (`scrapers/elite_prospects.py`)

- **Table:** `player_stats`
- **Columns:** `elc_flag` (bool), `contract_year_flag` (bool)
- **Frequency:** Weekly via `scrape-projections.yml`
- **Requires:** `ELITE_PROSPECTS_API_KEY` env var (free tier at eliteprospects.com/api)
- **Note:** Field names (`firstName`, `lastName`, `contract.type`, `contract.expiryYear`) are approximate — verify against live API before use.

#### NHL EDGE (`scrapers/nhl_edge.py`) — Tier 3, Optional

- **Table:** `player_stats`
- **Columns:** `speed_bursts_22` (float), `top_speed` (float)
- **Frequency:** Weekly via `scrape-projections.yml`
- **Note:** Field names (`sprintBurstsPerGame`, `topSpeed`) are approximate — verify against live API before use.

---

#### DailyFaceoff (`pp_unit` upload)

DailyFaceoff is paste/upload only — no CLI. Use the upload UI or test via the API directly:

```bash
# Minimal test CSV (save as /tmp/df_pp_test.csv):
cat > /tmp/df_pp_test.csv <<'EOF'
Player,G,A,PPP,SOG,HIT,BLK,GP,PIM,PP_Unit
Connor McDavid,52,72,28,280,32,18,82,24,1
Leon Draisaitl,45,65,30,260,40,20,82,36,1
Nathan MacKinnon,42,68,25,250,28,22,82,28,2
EOF

# Call the upload endpoint (requires auth token):
curl -X POST http://localhost:8000/sources/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@/tmp/df_pp_test.csv" \
  -F "source_name=daily_faceoff" \
  -F "season=2025-26"
```

Verify:

```sql
-- pp_unit written to player_stats
SELECT p.name, ps.pp_unit
FROM player_stats ps
JOIN players p ON p.id = ps.player_id
WHERE ps.season = '2025-26'
  AND ps.pp_unit IS NOT NULL
ORDER BY ps.pp_unit;
-- Expect: McDavid and Draisaitl with pp_unit=1, MacKinnon with pp_unit=2

-- pp_unit must NOT appear in player_projections
SELECT COUNT(*) FROM player_projections pp
JOIN sources s ON s.id = pp.source_id
WHERE s.name = 'daily_faceoff'
  AND pp.season = '2025-26'
  AND pp.extra_stats ? 'pp_unit';
-- Expect: 0 rows
```

**Pass criteria:** `pp_unit` present in `player_stats` for uploaded players; absent from `player_projections`.

---

#### Full end-to-end check

After running all three stat scrapers, verify the feature columns needed for Phase 3b model training are populated:

```sql
SELECT
  p.name,
  ps.gp,
  ps.g,
  ps.ixg_per60,
  ps.g_minus_ixg,
  ps.xgf_pct_5v5,
  ps.cf_pct,
  ps.xgf_pct,
  ps.icf_per60,
  ps.scf_pct,
  ps.scf_per60,
  ps.p1_per60,
  ps.toi_ev,
  ps.toi_pp,
  ps.toi_sh,
  ps.pp_unit
FROM player_stats ps
JOIN players p ON p.id = ps.player_id
WHERE ps.season = '2025-26'
ORDER BY ps.ixg_per60 DESC NULLS LAST
LIMIT 20;
```

A healthy result has the top 20 players with most columns non-null. `toi_pp` / `pp_unit` will be null for players with no PP time, which is expected.

---

## 7. ML Model

### Label Definition (CRITICAL)

- **Breakout:** +20% increase in **rate-adjusted real production** vs trailing 2-season average
  - Rate-adjusted = per-60 or per-game metrics (G, primary assists, shots, TOI)
  - **NOT fantasy-specific** — fantasy scoring is a downstream translation layer
- **Regression:** -20% decline in rate-adjusted real production
- **Neutral:** between -20% and +20%

### Feature Groups

1. **Production history:** G, A, Pts, PPP per 60 — last 3 seasons
2. **Usage/deployment:** TOI/game, PP time, zone starts, line position
3. **Efficiency metrics:** xGF%, CF%, HDCF%, on-ice SH% vs career SH%, iSCF/60
4. **Aging curves:** Age, years in league, historical comps at same age
5. **Injury history:** Games missed per season, injury type, recency
6. **Linemate quality:** Teammates' average xGF%, line combination history
7. **Contract context:** Contract year (motivation proxy), entry-level vs vet
8. **Situation changes:** Team trade activity, coach change, PP role shift

### Tier 1 Features (Highest Predictive Value)

- `iscf_per_60` — individual scoring chances per 60 (MOST UNDERUTILIZED)
- `xgf_pct` — expected goals for percentage
- G-minus-ixG gap (actual goals minus individual expected goals)
- On-ice SH% vs career SH% delta
- Age + years in league

### Regression Detection (3-part signal)

1. G-minus-ixG gap > threshold (scoring above expected)
2. SH% vs career average + 2 std devs (unsustainable shooting)
3. PDO > 1.03 (historically mean-reverts)

### Excluded Metrics (DO NOT USE)

- Takeaways/giveaways — arena scorer bias, not comparable across rinks
- Plus/minus — structural flaws, not indicative of player quality

### Serving Pattern

```python
import joblib
from fastapi import FastAPI

app = FastAPI()
model = None
shap_explainer = None

@app.on_event("startup")
def load_model():
    global model, shap_explainer
    model = joblib.load("ml/pucklogic_model.joblib")
    shap_explainer = joblib.load("ml/shap_explainer.joblib")

# Pre-computed SHAP values stored in player_trends.shap_values (JSONB)
# NOT computed per request — too slow for real-time serving
# Batch re-scoring via Celery nightly task

@app.get("/api/players/{player_id}/trends")
async def get_player_trends(player_id: str):
    # Read pre-computed scores from player_trends table
    # SHAP values included in response for frontend explainability UI
    ...
```

### Training Data Sources

| Source | Data | Notes |
|--------|------|-------|
| Hockey Reference | Season-level stats, 2008–2025 | Free |
| MoneyPuck | xG data, CSV archives from 2015+ | Free |
| Natural Stat Trick | Game logs, advanced stats from 2008+ | Free |
| Evolving Hockey | WAR/RAPM | $5/mo — subscribe before Phase 3 |
| CapFriendly/PuckPedia | Contract status | Free |

### Retraining Schedule

- **Yearly:** Pre-season (August), full retrain on updated historical data
- **Nightly:** Batch re-scoring Oct–Mar via Celery task → updates `player_trends` table
- **SHAP values:** Re-computed on retrain, NOT nightly (stored, not live)

---

## 8. Export Generation

| Type | Library | Trigger | Delivery |
|------|---------|---------|---------|
| PDF — Print & Draft | WeasyPrint | `POST /exports/generate` (`export_type: pdf`) | Streaming bytes — browser download |
| Excel — Draft Kit | openpyxl | `POST /exports/generate` (`export_type: excel`) | Streaming bytes — browser download |

Exports are read-only outputs — no import slots, no VBA. Users may export as many times as they want with any weight configuration at no additional cost.

**Excel — 2 sheets:**
- **Sheet 1 — "Full Rankings {season}":** Rank, Player, Team, Pos, FanPts, VORP, ScheduleScore, OffNightGames, SourceCount, then all stat columns (skater stats, then goalie stats; null = `—`).
- **Sheet 2 — "By Position":** Players grouped by position (C, LW, RW, D, G) with a header row per group. Same columns as Sheet 1.

Header block on both sheets: league settings, source weights used, PuckLogic Recommended flag, generated date and season.

**PDF — Print & Draft:** Full player rankings with blank checkbox column for pen-marking taken players; static best-available summary by position (snapshot at export time); league settings and source weights printed at top; generated date and season. Designed for offline drafts.

**`ExportRequest`** schema fields: `season`, `source_weights`, `scoring_config_id`, `platform`, `league_profile_id` (optional). `generate_excel()` and `generate_pdf()` in `services/exports.py` accept and render: fantasy points, VORP, off-night games, full `projected_stats` object.

Exports are synchronous streaming responses — no Celery job or Supabase Storage upload. `services/exports.py` exposes `generate_excel(ranked, season)` and `generate_pdf(ranked, season)` which return raw bytes; the router wraps them in `StreamingResponse` with the appropriate `Content-Disposition: attachment` header.

---

## 9. Environment Variables

```bash
# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...   # NEVER expose to frontend

# Redis (Upstash)
REDIS_URL=redis://xxx:xxx@xxx.upstash.io:6379

# Stripe
STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
STRIPE_PRICE_DRAFT_SESSION=price_xxx   # $2.99 per draft session
STRIPE_PRICE_EXPORT=price_xxx          # $1-3 per export

# ML
MODEL_PATH=./ml/pucklogic_model.joblib
SHAP_PATH=./ml/shap_explainer.joblib

# Scraper alerts
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx

# App
CORS_ORIGINS=https://pucklogic.com,chrome-extension://xxx
SESSION_SECRET=xxx
```

---

## 10. Player Name/ID Matching

- `nhl_id` from NHL.com API is the canonical player key
- `player_aliases` table maps variant names → canonical player_id + source
- **Resolution order:** exact match → fuzzy match (rapidfuzz, >90% similarity) → flag for admin review
- Admin UI surfaces unmatched players with suggested matches
- Runs at ingestion time, not query time
- Alias entries added on first successful fuzzy match

---

## 11. Anonymous-to-Authenticated Migration

```python
# On login/register: migrate anonymous kits to user account
async def migrate_session_kits(session_token: str, user_id: str):
    await db.execute(
        "UPDATE user_kits SET user_id = :user_id, session_token = NULL "
        "WHERE session_token = :session_token",
        {"user_id": user_id, "session_token": session_token}
    )
```

- Anonymous kits expire after 7 days (cron cleanup job)
- Session token stored in cookie (`pucklogic_session`, UUID)

---

## 12. Testing Conventions

- **Framework:** pytest + pytest-asyncio + pytest-cov
- **Async mode:** `asyncio_mode = "auto"` in `pyproject.toml`
- **File location:** `tests/` mirrors `apps/api/` structure
- **Fixtures:** `tests/conftest.py` (shared DB mocks, Supabase mock client)
- **Mocking:** `MagicMock` / `AsyncMock` for all I/O — never hit real DB or HTTP in unit tests
- **Coverage:** Run `pytest --cov` from `apps/api/`
- **Pre-commit:** ruff lint runs on all `.py` files before commit
