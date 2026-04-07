# PUCKLOGIC — Claude Code Context Reference
# Location: docs/claude-code-reference.md (repo root)
# 
# CLAUDE CODE INSTRUCTIONS:
# This file is the project-wide technical reference for PuckLogic.
# Read this file at the start of every session. Use it alongside the
# Notion ticket provided by the developer for the current task.
#
# The Notion ticket tells you WHAT to build (acceptance criteria, context).
# This file tells you HOW to build it (tech stack, patterns, schema, constraints).
#
# Section index (scan to find what's relevant to the current ticket):
#   SECTION: PROJECT STRUCTURE    — monorepo layout, dependencies
#   SECTION: DATABASE SCHEMA      — Supabase tables, RLS policies
#   SECTION: SCRAPER PATTERNS     — data ingestion, GitHub Actions cron
#   SECTION: RANKINGS AGGREGATION — algorithm, scoring translation
#   SECTION: ML MODEL             — features, labels, serving pattern
#   SECTION: EXTENSION ARCH       — platform adapters, WebSocket, MV3
#   SECTION: API ENDPOINTS        — FastAPI route map
#   SECTION: ENVIRONMENT          — env vars, secrets

# ============================================================================
# SECTION: PROJECT STRUCTURE
# Relevant to: all tasks
# ============================================================================

## Monorepo Layout (Turborepo)
```
pucklogic/
├── apps/
│   ├── web/                    # Next.js 14+ (App Router) — Vercel
│   │   ├── app/                # App Router pages
│   │   ├── components/         # Web-only components
│   │   └── lib/                # Web-only utilities
│   ├── api/                    # FastAPI (Python) — Railway/Fly.io
│   │   ├── routers/            # API route modules
│   │   ├── services/           # Business logic
│   │   ├── models/             # Pydantic models + SQLAlchemy
│   │   ├── scrapers/           # Data source scrapers
│   │   ├── ml/                 # ML model, training, inference
│   │   └── tasks/              # Celery background tasks
│   └── extension/              # Chrome MV3 extension
│       ├── manifest.json
│       ├── content_scripts/    # Platform adapters (ESPN, Yahoo)
│       ├── background/         # Service worker
│       ├── sidebar/            # React sidebar (shadow DOM)
│       └── popup/              # Extension popup
├── packages/
│   └── ui/                     # Shared React components
│       ├── PlayerCard/
│       ├── RankingsTable/
│       └── SuggestionPanel/
├── docs/
│   ├── research/
│   │   └── 001-nhl-advanced-stats-research.md  # NHL advanced stats research
│   ├── feature-engineering-spec.md  # ML feature spec
│   └── claude-code-reference.md    # THIS FILE
├── turbo.json
└── package.json
```

## Key Dependencies
- **Frontend:** next@14+, react@18+, tailwindcss, @shadcn/ui, zustand, swr
- **Backend:** fastapi, uvicorn, sqlalchemy, supabase-py, celery, redis, pydantic
- **ML:** xgboost or lightgbm, scikit-learn, pandas, numpy, shap, joblib, mlflow
- **Scrapers:** beautifulsoup4, requests, playwright (for JS-rendered sites)
- **Exports:** weasyprint (PDF), openpyxl (Excel)
- **Extension:** react, @anthropic-ai/sdk (if needed), chrome-types
- **Matching:** rapidfuzz (fuzzy string matching)

# ============================================================================
# SECTION: DATABASE SCHEMA
# Relevant to: all backend tasks, schema work, RLS, migrations
# ============================================================================

## Supabase PostgreSQL Schema

```sql
-- Player identity
CREATE TABLE players (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nhl_id INTEGER UNIQUE,          -- NHL.com player ID (canonical)
  name TEXT NOT NULL,
  team TEXT,
  position TEXT,                   -- C, LW, RW, D
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

CREATE TABLE player_rankings_staging (
  -- Same schema as player_rankings, used for atomic swap pattern
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
  breakout_score FLOAT,           -- 0-1 probability
  regression_risk FLOAT,          -- 0-1 probability
  confidence FLOAT,               -- model confidence
  shap_values JSONB,              -- pre-computed SHAP explanations
  projected_stats JSONB,          -- {g: 30, a: 45, pts: 75, ...}
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(player_id)
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
  user_id UUID REFERENCES auth.users(id),  -- NULL for anonymous
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
  status TEXT DEFAULT 'active',
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

## RLS Policy Patterns
```sql
-- Public read for player data
ALTER TABLE players ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read" ON players FOR SELECT USING (true);

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
```

# ============================================================================
# SECTION: SCRAPER PATTERNS
# Relevant to: Phase 1 scraper tasks, data pipeline, GitHub Actions
# ============================================================================

## Scraper Architecture Pattern
```python
# All scrapers follow this pattern:
# 1. Fetch data from source
# 2. Normalize to common format
# 3. Match player names to canonical IDs
# 4. Write to staging table
# 5. On success: atomic swap to production
# 6. On failure: discard staging, alert

from abc import ABC, abstractmethod

class BaseScraper(ABC):
    @abstractmethod
    def fetch_raw(self) -> list[dict]:
        """Fetch raw data from source. Returns list of player dicts."""
        pass

    @abstractmethod
    def normalize(self, raw: list[dict]) -> list[dict]:
        """Normalize to common schema: {name, rank, score, ...}"""
        pass

    def run(self):
        raw = self.fetch_raw()
        normalized = self.normalize(raw)
        matched = self.match_players(normalized)  # uses player_aliases
        self.write_staging(matched)
        self.promote_to_production()  # atomic swap

    def match_players(self, data):
        """Resolve player names to canonical IDs via fuzzy matching."""
        # 1. Exact match on player_aliases
        # 2. Fuzzy match (rapidfuzz, threshold >90%)
        # 3. Flag unmatched for manual review
        pass
```

## GitHub Actions Cron Pattern
```yaml
# .github/workflows/daily-scrape.yml
name: Daily Data Refresh
on:
  schedule:
    - cron: '0 6 * * *'  # 6 AM UTC daily
  workflow_dispatch:       # manual trigger

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -r requirements.txt
      - run: python -m scrapers.nhl_api
      - run: python -m scrapers.moneypuck
      - run: python -m scrapers.nst
    # On failure: send notification
    - if: failure()
      uses: slackapi/slack-github-action@v1
      with:
        webhook: ${{ secrets.SLACK_WEBHOOK }}
```

# ============================================================================
# SECTION: RANKINGS AGGREGATION
# Relevant to: Phase 2 aggregation, dashboard, kit building
# ============================================================================

## Aggregation Algorithm
```python
def aggregate_rankings(source_weights: dict[str, float], players: list) -> list:
    """
    source_weights: {source_id: weight} where weights sum to 1.0
    Returns sorted list of players with composite scores.
    """
    for player in players:
        available_sources = {s: w for s, w in source_weights.items()
                           if player.has_ranking(s)}
        # Redistribute weights for missing sources
        total_weight = sum(available_sources.values())
        normalized = {s: w/total_weight for s, w in available_sources.items()}

        # Compute composite score
        score = sum(
            player.get_normalized_rank(s) * w
            for s, w in normalized.items()
        )
        player.composite_score = score

    return sorted(players, key=lambda p: p.composite_score, reverse=True)
```

## Scoring Translation
```python
def translate_to_fantasy_points(projected_stats: dict, scoring_config: dict) -> float:
    """
    projected_stats: {g: 30, a: 45, ppp: 20, sog: 250, hits: 100, ...}
    scoring_config: {g: 3, a: 2, ppp: 1, sog: 0.5, hits: 0.5, ...}
    Returns: total projected fantasy points
    """
    return sum(
        projected_stats.get(stat, 0) * weight
        for stat, weight in scoring_config.items()
    )
```

# ============================================================================
# SECTION: ML MODEL
# Relevant to: Phase 3 ML tasks, feature engineering, training, inference
# ============================================================================

## Label Definition (CRITICAL)
- Breakout: +20% increase in RATE-ADJUSTED REAL PRODUCTION vs trailing 2-season avg
  - Rate-adjusted = per-60 or per-game metrics (not raw totals)
  - Stats: goals, primary assists, shots per 60, ice time
  - NOT fantasy-specific — fantasy scoring is a downstream translation layer
- Regression: -20% decline in rate-adjusted real production
- Neutral: between -20% and +20%

## Feature Engineering Reference
See docs/specs/007-feature-engineering-spec.md for full spec. Key points:

### Tier 1 Features (Highest Predictive Value)
- iSCF/60 (individual scoring chances per 60) — MOST UNDERUTILIZED
- xGF% (expected goals for percentage)
- G-minus-ixG gap (actual goals minus individual expected goals)
- On-ice SH% vs career SH% delta
- Age + years in league

### Tier 2 Features
- TOI/game, PP TOI, zone starts
- CF%, HDCF%
- PDO (SH% + SV%, historically mean-reverts)
- Linemate quality (teammates' avg xGF%)

### Regression Detection Signal (3-part)
1. G-minus-ixG gap > threshold (scoring above expected)
2. SH% vs career avg + 2 std devs (unsustainable shooting)
3. PDO > 1.03 (historically mean-reverts)

### Excluded Metrics
- Takeaways/giveaways (arena scorer bias — DO NOT USE)
- Plus/minus (structural flaws — DO NOT USE)

## Model Serving Pattern
```python
# FastAPI startup: load model once
import joblib
from fastapi import FastAPI

app = FastAPI()
model = None
shap_explainer = None

@app.on_event("startup")
def load_model():
    global model, shap_explainer
    model = joblib.load("pucklogic_model.joblib")
    shap_explainer = joblib.load("shap_explainer.joblib")

@app.get("/api/trends/{player_id}")
def get_player_trend(player_id: str):
    # Read from pre-computed player_trends table
    # SHAP values are pre-computed and stored, not computed per-request
    pass
```

# ============================================================================
# SECTION: EXTENSION ARCHITECTURE
# Relevant to: Phase 4 extension tasks, pick detection, sidebar, WebSocket
# ============================================================================

## Platform Adapter Pattern
```typescript
// content_scripts/adapters/types.ts
interface PlatformAdapter {
  detectPicks(callback: (pick: Pick) => void): void;
  extractPlayerName(element: HTMLElement): string | null;
  getDraftRoomState(): DraftState;
  getLeagueConfig(): LeagueConfig;
  cleanup(): void;
}

interface Pick {
  pickNumber: number;
  playerName: string;
  team?: string;
  position?: string;
}

// content_scripts/adapters/espn.ts
class ESPNAdapter implements PlatformAdapter { ... }

// content_scripts/adapters/yahoo.ts
class YahooAdapter implements PlatformAdapter { ... }

// content_scripts/index.ts
function getAdapter(): PlatformAdapter {
  const host = window.location.hostname;
  if (host.includes('espn.com')) return new ESPNAdapter();
  if (host.includes('yahoo.com')) return new YahooAdapter();
  throw new Error(`Unsupported platform: ${host}`);
}
```

## Extension Manifest (MV3)
```json
{
  "manifest_version": 3,
  "name": "PuckLogic Draft Monitor",
  "permissions": ["storage", "activeTab"],
  "host_permissions": [
    "*://*.espn.com/*",
    "*://*.yahoo.com/*"
  ],
  "content_scripts": [{
    "matches": [
      "*://fantasy.espn.com/hockey/draft*",
      "*://basketball.fantasysports.yahoo.com/hockey/*/draft*"
    ],
    "js": ["content_script.js"]
  }],
  "background": {
    "service_worker": "background.js"
  },
  "action": {
    "default_popup": "popup.html"
  }
}
```

## WebSocket Reconnection Pattern
```typescript
// background/websocket.ts
// CRITICAL: MV3 service workers can be terminated by Chrome when idle
// Must implement reconnection with state recovery

class DraftConnection {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnect = 5;
  private sessionId: string;

  connect(sessionId: string) {
    this.sessionId = sessionId;
    this.ws = new WebSocket(`wss://api.pucklogic.com/ws/draft/${sessionId}`);

    this.ws.onclose = () => {
      if (this.reconnectAttempts < this.maxReconnect) {
        const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 30000);
        setTimeout(() => this.connect(sessionId), delay);
        this.reconnectAttempts++;
      }
    };

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      // Request full state recovery on reconnect
      this.ws.send(JSON.stringify({ type: 'sync_state' }));
    };
  }
}
```

# ============================================================================
# SECTION: API ENDPOINTS
# Relevant to: all backend and frontend integration tasks
# ============================================================================

## FastAPI Route Structure
```
POST   /api/auth/login              — Supabase JWT login
POST   /api/auth/register           — Create account + migrate session kits

GET    /api/rankings                 — Aggregated rankings (accepts source_weights query)
GET    /api/rankings/sources         — Available ranking sources
POST   /api/kits                     — Save kit (auth or session_token)
GET    /api/kits                     — List user's kits
GET    /api/kits/{id}                — Get specific kit
PUT    /api/kits/{id}                — Update kit
DELETE /api/kits/{id}                — Delete kit

GET    /api/players                  — Player list with search/filter
GET    /api/players/{id}             — Player detail with stats
GET    /api/players/{id}/trends      — Player trend data + SHAP explanation

GET    /api/trends/breakouts         — Top breakout candidates
GET    /api/trends/regressions       — Regression watchlist

GET    /api/scoring/presets          — Available scoring presets
POST   /api/scoring/custom           — Save custom scoring config

POST   /api/exports/pdf              — Generate PDF cheat sheet (async)
POST   /api/exports/excel            — Generate Excel workbook (async)
GET    /api/exports/{id}/status      — Check export status
GET    /api/exports/{id}/download    — Download completed export

POST   /api/draft/session            — Create draft session (requires payment)
GET    /api/draft/session/{id}       — Get session state
WS     /ws/draft/{session_id}        — WebSocket for live draft

POST   /api/stripe/checkout          — Create Stripe checkout session
POST   /api/stripe/webhook           — Stripe webhook handler
```

# ============================================================================
# SECTION: ENVIRONMENT & SECRETS
# Relevant to: setup, deployment, CI/CD
# ============================================================================

## Required Environment Variables
```bash
# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# Redis (Upstash)
REDIS_URL=redis://xxx:xxx@xxx.upstash.io:6379

# Stripe
STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
STRIPE_PRICE_ID=price_xxx          # $2.99 draft session

# ML
MODEL_PATH=./ml/pucklogic_model.joblib
SHAP_PATH=./ml/shap_explainer.joblib

# Scraper alerts
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx

# App
CORS_ORIGINS=https://pucklogic.com,chrome-extension://xxx
SESSION_SECRET=xxx
```

# ============================================================================
# SECTION: CLAUDE CODE WORKFLOW
# Relevant to: all tasks
# ============================================================================

## How This Integrates With Claude Code

### In CLAUDE.md (repo root), add:
```
# PuckLogic Draft Kit

## Project Context
Read docs/claude-code-reference.md for full technical context (schema, patterns, stack).
Read docs/specs/007-feature-engineering-spec.md for ML feature details (Phase 3 only).
Read docs/research/001-nhl-advanced-stats-research.md for NHL advanced stats rationale.

## Working Conventions
- Use opusplan mode for major features, Sonnet for day-to-day work
- Each task maps to a Notion ticket — the developer will paste or link the ticket
- The Notion ticket has acceptance criteria (what to build) and context notes
- This reference doc has patterns and constraints (how to build it)
- Always check acceptance criteria checkboxes against your implementation
- Run tests before marking any task complete
```

### Workflow per task:
1. Developer pastes Notion ticket content (or links it) into Claude Code
2. Claude Code reads this reference doc from docs/claude-code-reference.md
3. Claude Code cross-references the ticket's phase/domain against section headers
4. Claude Code implements against acceptance criteria, using patterns from this doc
5. Developer verifies and checks off acceptance criteria in Notion
