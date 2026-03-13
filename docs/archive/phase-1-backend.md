# PuckLogic Phase 1 — Backend Implementation

## Foundation — Monorepo Scaffold, Database Schema, and Core Scrapers

**Timeline:** March – April 2026 (Phase 1)
**Target Release:** v1.0 (September 2026)
**Reference:** `pucklogic_architecture.docx` · `CLAUDE.md`

---

## Overview

Phase 1 backend establishes the **project foundation**: Turborepo monorepo structure, Supabase PostgreSQL schema, NHL.com and MoneyPuck scrapers, GitHub Actions cron jobs, Supabase Auth with Row Level Security, and a FastAPI skeleton with auth middleware.

**Deliverables:**
1. ✅ Turborepo monorepo scaffold (`apps/web`, `apps/api`, `packages/ui`, `packages/extension`)
2. ✅ Supabase PostgreSQL schema — all core tables created and migrated
3. ✅ NHL.com official API scraper (players, rosters, stats, game logs)
4. ✅ MoneyPuck CSV scraper (xG, shot data, advanced metrics)
5. ✅ GitHub Actions cron jobs for daily scraper runs
6. ✅ Supabase Auth setup (JWT, Row Level Security policies)
7. ✅ FastAPI skeleton with health check, CORS, and auth middleware
8. ✅ Test coverage (pytest, mocked HTTP)

---

## 1. Database Schema

### 1.1 Core Tables

All tables are created via Supabase migrations in `supabase/migrations/001_initial_schema.sql`.

```sql
-- players: NHL player master
CREATE TABLE players (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nhl_id INTEGER UNIQUE NOT NULL,
  name TEXT NOT NULL,
  team TEXT,
  position TEXT CHECK (position IN ('C','LW','RW','D','G')),
  dob DATE,
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- player_stats: raw stats per player per season
CREATE TABLE player_stats (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  player_id UUID REFERENCES players(id) ON DELETE CASCADE,
  season TEXT NOT NULL,           -- e.g. "2024-25"
  games_played INTEGER,
  goals INTEGER,
  assists INTEGER,
  plus_minus INTEGER,
  pim INTEGER,
  ppg INTEGER,
  ppa INTEGER,
  shg INTEGER,
  sha INTEGER,
  gwg INTEGER,
  fow INTEGER,
  fol INTEGER,
  shifts INTEGER,
  hat_tricks INTEGER,
  sog INTEGER,
  hits INTEGER,
  blocked_shots INTEGER,
  -- advanced metrics
  toi_per_game NUMERIC,
  cf_pct NUMERIC,                 -- Corsi for %
  xgf_pct NUMERIC,               -- expected goals for %
  shooting_pct NUMERIC,
  source TEXT NOT NULL,           -- 'nhl_com' | 'moneypuck' | 'nst'
  scraped_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (player_id, season, source)
);

-- player_rankings: per-source rankings
CREATE TABLE player_rankings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  player_id UUID REFERENCES players(id) ON DELETE CASCADE,
  source TEXT NOT NULL,
  rank INTEGER NOT NULL,
  score NUMERIC,
  season TEXT NOT NULL,
  scraped_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (player_id, source, season)
);

-- player_trends: ML output (populated in Phase 3 and v2.0)
CREATE TABLE player_trends (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  player_id UUID REFERENCES players(id) ON DELETE CASCADE,
  season TEXT NOT NULL,
  -- Layer 1 (Phase 3)
  breakout_score NUMERIC,
  regression_risk NUMERIC,
  confidence TEXT CHECK (confidence IN ('HIGH','MEDIUM','LOW')),
  shap_json JSONB,
  -- Layer 2 (v2.0)
  trending_up_score NUMERIC,
  trending_down_score NUMERIC,
  momentum_score NUMERIC,
  signals_json JSONB,
  window_days INTEGER DEFAULT 14,
  -- Combined
  pucklogic_trends_score NUMERIC,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (player_id, season)
);

-- sources: registered aggregation sources
CREATE TABLE sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT UNIQUE NOT NULL,
  url TEXT,
  scrape_config JSONB,
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- user_kits: saved user weighting configs
CREATE TABLE user_kits (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  weights JSONB NOT NULL,
  league_format TEXT CHECK (league_format IN ('points','roto','head_to_head')) DEFAULT 'points',
  scoring_settings JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- subscriptions: Stripe subscription state
CREATE TABLE subscriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
  stripe_customer_id TEXT,
  stripe_subscription_id TEXT,
  plan TEXT CHECK (plan IN ('free','pro','draft_session')) DEFAULT 'free',
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- draft_sessions: live draft state (stub — fully used in Phase 4)
CREATE TABLE draft_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  league_config JSONB NOT NULL,
  picks JSONB DEFAULT '[]',
  available JSONB,
  status TEXT CHECK (status IN ('active','completed','abandoned')) DEFAULT 'active',
  stripe_payment_intent_id TEXT,
  started_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- exports: export job records (stub — fully used in Phase 2)
CREATE TABLE exports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  type TEXT CHECK (type IN ('pdf','excel')),
  status TEXT CHECK (status IN ('pending','complete','failed')) DEFAULT 'pending',
  storage_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- injury_reports: injury tracking (stub — fully used in v2.0)
CREATE TABLE injury_reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  player_id UUID REFERENCES players(id) ON DELETE CASCADE,
  status TEXT CHECK (status IN ('healthy','day_to_day','injured_reserve','long_term_ir')),
  description TEXT,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (player_id)
);
```

### 1.2 Row Level Security Policies

```sql
-- players, player_stats, player_rankings, player_trends, sources: public read
ALTER TABLE players ENABLE ROW LEVEL SECURITY;
CREATE POLICY "public_read_players" ON players FOR SELECT USING (true);
CREATE POLICY "service_write_players" ON players FOR ALL USING (auth.role() = 'service_role');

-- (same pattern for player_stats, player_rankings, player_trends, sources)

-- user_kits: users can CRUD their own rows
ALTER TABLE user_kits ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users_own_kits" ON user_kits
  FOR ALL USING (auth.uid() = user_id);

-- subscriptions: users can read their own row; service-role writes
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users_read_own_subscription" ON subscriptions
  FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "service_write_subscriptions" ON subscriptions
  FOR ALL USING (auth.role() = 'service_role');

-- draft_sessions, exports: users own their own rows
ALTER TABLE draft_sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users_own_sessions" ON draft_sessions FOR ALL USING (auth.uid() = user_id);

ALTER TABLE exports ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users_own_exports" ON exports FOR ALL USING (auth.uid() = user_id);
```

---

## 2. Scrapers

### 2.1 NHL.com API Scraper

**Location:** `apps/api/src/scrapers/nhl_com.py`

The NHL.com scraper uses the official `api-web.nhle.com` API (no key required). It is the single source covering all 23 ESPN fantasy scoring categories.

```python
import httpx
import asyncio
from dataclasses import dataclass

class NhlComScraper:
    BASE_URL = "https://api-web.nhle.com/v1"
    RATE_LIMIT_DELAY = 2.0  # seconds between requests

    def __init__(self, supabase_client):
        self.db = supabase_client

    async def _get(self, path: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.BASE_URL}{path}", timeout=30)
            resp.raise_for_status()
            await asyncio.sleep(self.RATE_LIMIT_DELAY)
            return resp.json()

    async def fetch_roster(self, team_abbr: str, season: str) -> list[dict]:
        """Returns list of player objects for a team's roster."""
        data = await self._get(f"/roster/{team_abbr}/{season}")
        return data.get("forwards", []) + data.get("defensemen", []) + data.get("goalies", [])

    async def fetch_skater_stats(self, player_id: int, season: str) -> dict:
        """Fetches current-season stats for a single skater."""
        data = await self._get(f"/player/{player_id}/landing")
        # Extract season stats from featuredStats or seasonTotals
        for entry in data.get("seasonTotals", []):
            if entry["season"] == int(season.replace("-", "")):
                return entry
        return {}

    async def fetch_game_log(self, player_id: int, season: str) -> list[dict]:
        """Game-by-game log for hat trick counting (games with 3+ goals)."""
        data = await self._get(f"/player/{player_id}/game-log/{season}/2")
        return data.get("gameLog", [])

    async def fetch_all_players(self, season: str) -> list[dict]:
        """Bulk skater summary via /skater/summary endpoint."""
        data = await self._get(f"/skater/summary?season={season}&limit=1000")
        return data.get("data", [])

    async def fetch_realtime_stats(self, season: str) -> list[dict]:
        """Hits and blocked shots from /skater/realtime."""
        data = await self._get(f"/skater/realtime?season={season}&limit=1000")
        return data.get("data", [])
```

**Endpoints used:**

| Endpoint | Data |
|----------|------|
| `/roster/{team}/{season}` | Team roster |
| `/player/{id}/landing` | Player profile + current season stats |
| `/player/{id}/game-log/{season}/2` | Game-by-game log (hat trick counting) |
| `/skater/summary?season={season}` | Goals, assists, +/-, PIM, PPG, PPP, SHG, SHP, GWG, SOG, shifts |
| `/skater/realtime?season={season}` | Hits, blocked shots |

**Rate limiting & ethics:** 2-second delay between all requests. Respects `robots.txt`. Never bypasses rate limits.

### 2.2 MoneyPuck CSV Scraper

**Location:** `apps/api/src/scrapers/moneypuck.py`

MoneyPuck provides public CSV downloads of advanced skater metrics. No authentication required.

```python
import httpx
import pandas as pd
import io

class MoneyPuckScraper:
    CSV_BASE = "https://moneypuck.com/moneypuck/playerData/seasonSummary"
    RATE_LIMIT_DELAY = 3.0

    async def fetch_skater_csv(self, season: str) -> pd.DataFrame:
        """
        Downloads the all-situations skater CSV for a given season.
        Season format: '2024' (start year of the season).
        """
        url = f"{self.CSV_BASE}/{season}/regular/skaters.csv"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=60)
            resp.raise_for_status()

        df = pd.read_csv(io.StringIO(resp.text))
        # Filter to 'all' situation for primary stats
        return df[df["situation"] == "all"]

    async def upsert_stats(self, df: pd.DataFrame, season: str) -> int:
        """Upserts MoneyPuck stats to player_stats table. Returns rows upserted."""
        rows = []
        for _, row in df.iterrows():
            rows.append({
                "player_id": self._resolve_player_id(row["playerId"]),
                "season": season,
                "goals": int(row["goals"]),
                "assists": int(row["I_F_assists"]),
                "sog": int(row["shotsOnGoalFor"]),
                "xgf_pct": float(row["xGoalsPercentage"]),
                "cf_pct": float(row["corsiPercentage"]),
                "source": "moneypuck",
                "scraped_at": "now()",
            })
        self.db.table("player_stats").upsert(rows, on_conflict="player_id,season,source").execute()
        return len(rows)
```

**Columns extracted:**

| CSV Column | DB Column | Description |
|------------|-----------|-------------|
| `playerId` | — | NHL player ID (used for join) |
| `goals` | `goals` | Goals in all situations |
| `I_F_assists` | `assists` | Individual assists |
| `shotsOnGoalFor` | `sog` | Shots on goal |
| `xGoalsPercentage` | `xgf_pct` | Expected goals for % |
| `corsiPercentage` | `cf_pct` | Corsi for % |
| `xGoals` | — | Used for Layer 1 feature engineering |

---

## 3. GitHub Actions Cron Jobs

**Location:** `.github/workflows/`

### 3.1 Daily Scraper

```yaml
# .github/workflows/scrape-daily.yml
name: Daily Scraper
on:
  schedule:
    - cron: '0 11 * * *'   # 11:00 UTC = 6:00 AM ET
  workflow_dispatch:        # allow manual trigger

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -e ".[scraper]" --quiet
        working-directory: apps/api
      - name: Run daily scrape
        run: python -m src.jobs.daily_scrape
        working-directory: apps/api
    env:
      SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
      SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
```

### 3.2 Weekly Scrapers (Phase 3+)

A separate `scrape-weekly.yml` workflow runs on Sundays for less-frequent sources (DailyFaceoff, Elite Prospects, Hockey Reference). Defined as a stub in Phase 1.

---

## 4. FastAPI Application

### 4.1 App Factory

**Location:** `apps/api/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.middleware.auth import SupabaseAuthMiddleware
from src.routers import health, players

def create_app() -> FastAPI:
    app = FastAPI(title="PuckLogic API", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://pucklogic.com", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SupabaseAuthMiddleware)

    app.include_router(health.router)
    app.include_router(players.router, prefix="/api")

    return app

app = create_app()
```

### 4.2 Auth Middleware

**Location:** `apps/api/src/middleware/auth.py`

Validates Supabase JWTs on all `/api/*` routes. Health check (`/health`) is exempt.

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from jose import jwt, JWTError
import os

class SupabaseAuthMiddleware(BaseHTTPMiddleware):
    EXEMPT_PATHS = {"/health", "/webhooks/stripe"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.EXEMPT_PATHS or not request.url.path.startswith("/api"):
            return await call_next(request)

        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if not token:
            return Response("Unauthorized", status_code=401)

        try:
            payload = jwt.decode(
                token,
                os.environ["SUPABASE_JWT_SECRET"],
                algorithms=["HS256"],
                audience="authenticated",
            )
            request.state.user_id = payload["sub"]
        except JWTError:
            return Response("Unauthorized", status_code=401)

        return await call_next(request)
```

### 4.3 Core Routes

**Health check** (`GET /health`):
```python
@router.get("/health")
async def health():
    return {"status": "ok"}
```

**Players** (`GET /api/players`):
```python
@router.get("/players")
async def list_players(
    season: str = "2024-25",
    position: str | None = None,
    page: int = 1,
    limit: int = 50,
):
    """Paginated player list with optional season and position filters."""
    ...

@router.get("/players/{player_id}")
async def get_player(player_id: str):
    """Single player profile with career stats."""
    ...
```

---

## 5. Testing

### 5.1 Test Structure

```
apps/api/tests/
  conftest.py                     # shared fixtures, mock Supabase client
  test_health.py                  # FastAPI TestClient, assert 200 on /health
  scrapers/
    test_nhl_com.py               # mock httpx, assert correct player objects
    test_moneypuck.py             # mock CSV download, assert DataFrame parsing
  repositories/
    test_players.py               # mock Supabase, assert read/write operations
  middleware/
    test_auth.py                  # valid JWT passes, invalid JWT returns 401
```

### 5.2 Key Test Cases

```python
# tests/scrapers/test_nhl_com.py

@pytest.mark.asyncio
async def test_fetch_all_players_returns_list(mock_httpx):
    """Mocked NHL.com response returns a list of player dicts."""
    mock_httpx.return_value = {"data": [{"playerId": 1, "skaterFullName": "Connor McDavid"}]}
    scraper = NhlComScraper(supabase_client=MagicMock())
    players = await scraper.fetch_all_players("2024-25")
    assert len(players) == 1
    assert players[0]["skaterFullName"] == "Connor McDavid"

@pytest.mark.asyncio
async def test_fetch_game_log_counts_hat_tricks(mock_httpx):
    """Games with goals >= 3 are counted as hat tricks."""
    mock_httpx.return_value = {
        "gameLog": [
            {"goals": 3, "gameId": 1},
            {"goals": 1, "gameId": 2},
        ]
    }
    scraper = NhlComScraper(supabase_client=MagicMock())
    log = await scraper.fetch_game_log(player_id=8478402, season="2024-25")
    hat_tricks = sum(1 for g in log if g["goals"] >= 3)
    assert hat_tricks == 1


# tests/scrapers/test_moneypuck.py

@pytest.mark.asyncio
async def test_fetch_skater_csv_filters_to_all_situation(mock_httpx, sample_csv):
    """CSV download is filtered to situation == 'all'."""
    mock_httpx.return_value.text = sample_csv
    scraper = MoneyPuckScraper()
    df = await scraper.fetch_skater_csv("2024")
    assert all(df["situation"] == "all")

@pytest.mark.asyncio
async def test_upsert_stats_returns_row_count(mock_httpx, sample_df):
    """upsert_stats returns the number of rows written."""
    mock_db = MagicMock()
    scraper = MoneyPuckScraper()
    scraper.db = mock_db
    count = await scraper.upsert_stats(sample_df, "2024-25")
    assert count == len(sample_df)


# tests/test_health.py

def test_health_returns_ok():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# tests/middleware/test_auth.py

def test_missing_token_returns_401():
    client = TestClient(app)
    resp = client.get("/api/players")
    assert resp.status_code == 401

def test_valid_jwt_passes_middleware(valid_jwt):
    client = TestClient(app)
    resp = client.get("/api/players", headers={"Authorization": f"Bearer {valid_jwt}"})
    assert resp.status_code == 200
```

**Coverage target:** ≥ 80% for all Phase 1 modules.

---

## Appendix: Key Files

```
apps/api/
  main.py                              # FastAPI app factory
  pyproject.toml                       # dependencies, pytest config, ruff config
  src/
    scrapers/
      nhl_com.py                       # NHL.com API scraper
      moneypuck.py                     # MoneyPuck CSV scraper
    repositories/
      players.py                       # Player DB read/write helpers
      stats.py                         # Stats DB read/write helpers
    middleware/
      auth.py                          # Supabase JWT validation middleware
    routers/
      health.py                        # GET /health
      players.py                       # GET /api/players, GET /api/players/{id}
    jobs/
      daily_scrape.py                  # Entry point for GitHub Actions cron
  tests/
    conftest.py                        # Shared fixtures, mock Supabase client
    test_health.py
    scrapers/
      test_nhl_com.py
      test_moneypuck.py
    repositories/
      test_players.py
    middleware/
      test_auth.py

supabase/
  migrations/
    001_initial_schema.sql             # All tables + RLS policies

.github/
  workflows/
    scrape-daily.yml                   # Daily GitHub Actions cron (6 AM ET)
    scrape-weekly.yml                  # Weekly cron (stub, used Phase 3+)
```

### Environment Variables

```bash
# apps/api/.env
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_KEY=<service_role_key>
SUPABASE_JWT_SECRET=<jwt_secret>
```

Never commit `.env` files. Add to `.gitignore`.
