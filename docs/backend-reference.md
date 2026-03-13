# PuckLogic — Backend Reference

**Domain:** FastAPI backend (`apps/api/`)
**See also:** [pucklogic-architecture.md](pucklogic-architecture.md) for system overview

---

## 1. Project Structure

```
apps/api/
├── main.py                 # FastAPI app, startup, CORS
├── routers/
│   ├── rankings.py         # /api/rankings routes
│   ├── players.py          # /api/players routes
│   ├── trends.py           # /api/trends routes
│   ├── kits.py             # /api/kits routes
│   ├── exports.py          # /api/exports routes
│   ├── draft.py            # /api/draft routes + WebSocket
│   ├── scoring.py          # /api/scoring routes
│   ├── auth.py             # /api/auth routes
│   └── stripe.py           # /api/stripe routes
├── services/
│   ├── rankings.py         # Aggregation algorithm, Redis cache
│   ├── exports.py          # PDF/Excel generation
│   ├── draft.py            # Draft session management
│   └── scoring.py          # Scoring translation layer
├── models/
│   ├── players.py          # Pydantic models + SQLAlchemy
│   ├── rankings.py
│   ├── kits.py
│   └── exports.py
├── scrapers/
│   ├── base.py             # BaseScraper ABC
│   ├── nhl_api.py          # NHL.com official API
│   ├── moneypuck.py        # MoneyPuck CSV downloads
│   ├── nst.py              # Natural Stat Trick (BeautifulSoup)
│   ├── dobber.py           # Dobber Hockey (may need Playwright)
│   └── matching.py         # Player name/ID resolution (rapidfuzz)
├── ml/
│   ├── train.py            # Model training pipeline
│   ├── predict.py          # Batch inference, Celery task
│   ├── features.py         # Feature engineering
│   └── pucklogic_model.joblib  # Serialized XGBoost model
├── tasks/
│   ├── celery_app.py       # Celery config + Redis broker
│   ├── export_tasks.py     # Async export generation
│   └── ml_tasks.py         # Nightly re-scoring task
└── tests/
    ├── conftest.py
    ├── repositories/
    └── routers/
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
  last_successful_scrape TIMESTAMPTZ
);

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

CREATE TABLE player_projections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  player_id UUID REFERENCES players(id),
  season TEXT NOT NULL,
  projected_stats JSONB,          -- {g: 30, a: 45, pts: 75, ppp: 20, ...}
  scoring_basis TEXT,             -- 'rate_adjusted_2yr_avg' or similar
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(player_id, season)
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

CREATE TABLE user_kits (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id),  -- NULL for anonymous sessions
  session_token UUID,              -- for anonymous kit building
  name TEXT,
  source_weights JSONB NOT NULL,  -- {source_id: weight, ...}
  scoring_config_id UUID REFERENCES scoring_configs(id),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  CHECK (user_id IS NOT NULL OR session_token IS NOT NULL)
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
| player_projections, sources | Public (RLS) | Service role only |
| scoring_configs (is_preset=true) | Public (RLS) | Service role only |
| user_kits | Owner or matching session_token | Owner (API check) |
| draft_sessions | Owner (API check) | Owner (API check) |
| exports | Owner (API check) | Owner (API check) |
| subscriptions | Owner (API check) | Stripe webhook (service role) |
| scoring_configs (custom) | Owner (API check) | Owner (API check) |

---

## 4. API Routes

```
POST   /api/auth/login              — Supabase JWT login + migrate anon session kits
POST   /api/auth/register           — Create account, migrate session kits to user_id

GET    /api/rankings                 — Aggregated rankings (accepts source_weights query param)
POST   /api/rankings/compute         — Compute and cache rankings for a kit
GET    /api/rankings/sources         — Available active ranking sources

POST   /api/kits                     — Save kit (auth or session_token)
GET    /api/kits                     — List user's saved kits
GET    /api/kits/{id}                — Get specific kit
PUT    /api/kits/{id}                — Update kit weights/config
DELETE /api/kits/{id}                — Delete kit

GET    /api/players                  — Player list with search/filter (position, team)
GET    /api/players/{id}             — Player detail with current season stats
GET    /api/players/{id}/trends      — Player trend data + SHAP explanation

GET    /api/trends/breakouts         — Top breakout candidates (paginated)
GET    /api/trends/regressions       — Regression watchlist (paginated)

GET    /api/scoring/presets          — Available scoring presets
POST   /api/scoring/custom           — Save custom scoring config (auth required)

POST   /api/exports/pdf              — Enqueue PDF cheat sheet (async, Celery)
POST   /api/exports/excel            — Enqueue Excel workbook (async, Celery)
GET    /api/exports/{id}/status      — Poll export job status
GET    /api/exports/{id}/download    — Redirect to Supabase Storage URL

POST   /api/draft/session            — Create draft session (requires active subscription)
GET    /api/draft/session/{id}       — Get session state
WS     /ws/draft/{session_id}        — WebSocket for live draft updates

POST   /api/stripe/checkout          — Create Stripe checkout session (returns URL)
POST   /api/stripe/webhook           — Stripe webhook → upsert subscriptions table
```

### Auth Middleware Pattern

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from supabase import create_client

bearer_scheme = HTTPBearer(auto_error=False)

async def get_current_user(token: str = Depends(bearer_scheme)):
    if token is None:
        return None  # anonymous — some routes allow this
    user = supabase.auth.get_user(token.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

async def require_auth(user = Depends(get_current_user)):
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user
```

---

## 5. Rankings Aggregation Algorithm

```python
def aggregate_rankings(source_weights: dict[str, float], players: list) -> list:
    """
    source_weights: {source_id: weight} — weights must sum to 1.0
    Returns: players sorted by composite score (descending).
    Missing source data → weight redistributed to present sources.
    """
    for player in players:
        available_sources = {
            s: w for s, w in source_weights.items()
            if player.has_ranking(s)
        }
        # Graceful degradation: redistribute weights for absent sources
        total_weight = sum(available_sources.values())
        normalized = {s: w / total_weight for s, w in available_sources.items()}

        # Normalized rank: 1 = best, converted to 0-1 (1.0 = best)
        score = sum(
            player.get_normalized_rank(s) * w
            for s, w in normalized.items()
        )
        player.composite_score = score

    return sorted(players, key=lambda p: p.composite_score, reverse=True)


def translate_to_fantasy_points(projected_stats: dict, scoring_config: dict) -> float:
    """
    projected_stats: {g: 30, a: 45, ppp: 20, sog: 250, hits: 100, ...}
    scoring_config:  {g: 3,  a: 2,  ppp: 1,  sog: 0.5, hits: 0.5, ...}
    """
    return sum(
        projected_stats.get(stat, 0) * weight
        for stat, weight in scoring_config.items()
    )
```

**Caching:** Results cached in Upstash Redis for 6 hours. Manual refresh rate-limited: 10 req/min per user, IP-based for anonymous.

---

## 6. Scraper Patterns

### Base Scraper

```python
from abc import ABC, abstractmethod

class BaseScraper(ABC):
    @abstractmethod
    def fetch_raw(self) -> list[dict]:
        """Fetch raw data from source. Returns list of player dicts."""

    @abstractmethod
    def normalize(self, raw: list[dict]) -> list[dict]:
        """Normalize to common schema: {nhl_id, name, rank, score, season}"""

    def run(self):
        raw = self.fetch_raw()
        normalized = self.normalize(raw)
        matched = self.match_players(normalized)  # uses player_aliases + rapidfuzz
        self.write_staging(matched)
        self.promote_to_production()  # atomic swap

    def match_players(self, data: list[dict]) -> list[dict]:
        """
        Resolve player names to canonical IDs via:
        1. Exact match on player_aliases
        2. Fuzzy match (rapidfuzz, threshold >90%)
        3. Flag unmatched for admin review
        """
        ...

    def write_staging(self, data: list[dict]):
        """Write to player_rankings_staging (never directly to player_rankings)."""
        ...

    def promote_to_production(self):
        """
        Atomic swap: DELETE old rankings + INSERT new in a single transaction.
        On failure: staging discarded, production unchanged.
        """
        ...
```

### GitHub Actions Cron

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
      - run: python -m apps.api.scrapers.nhl_api
      - run: python -m apps.api.scrapers.moneypuck
      - run: python -m apps.api.scrapers.nst
    - if: failure()
      uses: slackapi/slack-github-action@v1
      with:
        webhook: ${{ secrets.SLACK_WEBHOOK }}
```

### Scraper Failure Handling

- Scrapers write to staging tables only
- Full success → atomic swap to production
- Any failure → discard staging, log error, serve stale data with "last updated X hours ago" badge
- GitHub Actions sends Slack/email alert on failure

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
| PDF cheat sheet | WeasyPrint | `POST /api/exports/pdf` | Supabase Storage (24hr TTL) |
| Excel workbook | openpyxl | `POST /api/exports/excel` | Supabase Storage (24hr TTL) |
| Bundle (PDF + Excel) | Both | `POST /api/exports/bundle` | Both links |

Exports are generated asynchronously via Celery. Multi-tab Excel: master rankings, by-position tabs, Trends tab (breakout/regression scores).

```python
# tasks/export_tasks.py
from celery import shared_task

@shared_task
def generate_pdf_export(export_id: str, kit_id: str, user_id: str):
    """
    1. Fetch ranked players for kit_id
    2. Generate PDF via WeasyPrint
    3. Upload to Supabase Storage
    4. Update exports.status = 'complete', set storage_url
    5. On failure: update exports.status = 'failed'
    """
    ...
```

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
