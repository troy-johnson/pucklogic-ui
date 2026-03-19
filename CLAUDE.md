# PuckLogic Draft Kit — Claude Code Context

## Project Overview

PuckLogic is a fantasy hockey draft kit targeting casual and competitive/keeper players.

**v1.0 (target: late October 2026)** — two products:
1. **Free rankings aggregator**: users select sources, assign weights, get a custom consensus ranking
2. **Paid real-time draft monitor**: Chrome browser extension with live best-available suggestions

The Trends engine (Layer 1 only) ships in v1.0 as pre-season breakout/regression scores overlaid on the rankings.

**v2.0 (post-launch)** — in-season leading indicator engine (Layer 2): 14-day rolling Z-scores for TOI, xGF%, Corsi, PP unit changes, line combos, etc. Surfaces players trending up *before* production shows up in standard stats.

Full architecture details: `docs/pucklogic-architecture.md`
ML feature engineering spec (Phase 3): `docs/feature-engineering-spec.md`
Stats research and methodology: `docs/stats-research.md`

---

## Tech Stack

| Layer | Technology |
|---|---|
| Monorepo | Turborepo |
| Frontend | Next.js 14+ (App Router), Tailwind CSS, shadcn/ui, Zustand, SWR |
| Backend | FastAPI (Python), Celery + Redis (background jobs) |
| Database | Supabase (PostgreSQL + Auth + Storage) |
| Cache | Upstash Redis (TTL-based ranking cache, 6h) |
| ML / Trends | XGBoost / LightGBM, scikit-learn, SHAP, joblib |
| Browser Extension | Chrome MV3, React (shared components from `packages/ui`) |
| Exports | WeasyPrint (PDF), openpyxl (Excel) |
| Payments | Stripe Checkout |
| Hosting | Vercel (frontend), Railway or Fly.io (backend) |

---

## Monorepo Structure

```
apps/
  web/          # Next.js 14+ frontend (App Router)
  api/          # FastAPI backend + ML inference
packages/
  ui/           # Shared React components (used by web + extension)
  extension/    # Chrome MV3 extension
docs/
  pucklogic-architecture.md  # System overview (start here)
  backend-reference.md       # DB DDL, API routes, scrapers, ML, exports
  frontend-reference.md      # App Router, auth, Zustand, SWR, components
  extension-reference.md     # MV3 manifest, adapters, service worker, popup
  archive/                   # Superseded per-phase docs
.claude/
  hooks/        # Claude Code session start hook
  settings.json
```

---

## Dev Commands

**From repo root (Turborepo)**
```bash
pnpm install         # install all workspace dependencies
pnpm run dev         # start all apps in dev mode (Next.js on :3000)
pnpm run build       # production build all apps
pnpm run lint        # lint all apps
pnpm run test        # run all tests
```

**Frontend only**
```bash
cd apps/web
pnpm run dev         # Next.js dev server on http://localhost:3000
```

**Backend (FastAPI)**
```bash
cd apps/api
pip install -e ".[dev]"         # install Python deps (first time)
uvicorn main:app --reload       # dev server on http://localhost:8000
pytest                          # run tests
ruff check .                    # lint
```

**Add a shadcn/ui component**
```bash
cd apps/web
npx shadcn@latest add <component-name>
```

---

## Key Architecture Decisions

- **Next.js over SvelteKit**: Chrome extension shares React components from `packages/ui` — a Svelte build would require a separate pipeline.
- **FastAPI over Node backend**: ML model (Python/XGBoost) runs in the same process — no cross-language serialization overhead for predictions.
- **Aggregation pipeline (stat-projection-based)**: projection sources publish per-player projected counting stats (G, A, PIM, SOG, hits, blocks, PPP, etc.) into `player_projections`. `POST /rankings/compute` computes a weighted average of each stat across sources (nulls excluded per-stat), applies the user's `scoring_config` → projected fantasy points, computes VORP relative to replacement-level per position, attaches a schedule score (off-night game count), and sorts by projected fantasy points descending. Results cached in Redis for 6h. Cache key includes a SHA-256 digest of `(source_weights, scoring_config_id, platform, league_profile_id)`; invalidated on every new source ingest via `invalidate_rankings(season)`.
- **`player_rankings` is not part of the aggregation pipeline.** The table is retained for potential future rank-only sources but is not read by `POST /rankings/compute`. NHL.com and MoneyPuck write to `player_stats` only — they are stat sources, not projection sources.
- **VORP**: `player.projected_fantasy_points − replacement_level.projected_fantasy_points` per position group. Primary position (`players.position`, NHL.com canonical) determines the position group. Replacement level = Nth ranked player where N = `(num_teams × position_slots) + 1`. Negative VORP is allowed. Requires `league_profile_id` in the request; omitting it returns `vorp: null` for all players.
- **Scoring config validation**: `PPP` and `PPG`/`PPA` cannot both be non-zero in the same config (same rule for `SHP`/`SHG`/`SHA`). Enforced at config creation time with HTTP 400.
- **`user_kits`**: retained as named source-weight presets only. Full league configuration (platform, num_teams, roster_slots, scoring_config_id) lives in `league_profiles`.
- **Draft monitor**: `MutationObserver` watches ESPN Fantasy DOM for pick events → service worker relays via WebSocket to backend → backend returns best-available suggestions.
- **Paywalled sources** (e.g. Dom Luszczyszyn): marked `is_paid=true` in `sources` table. For public users, paid source stat columns are present but empty — aggregation runs over free sources only. User uploads their own copy via paste/upload UI (2 custom source slots per user).
- **Extension monetization**: $2–3 one-time per draft session; payment via Stripe on the web app — no payment UI in the extension itself (simplifies Chrome Web Store compliance).

---

## Core Database Tables (Supabase PostgreSQL)

> Full DDL and RLS policies: `docs/backend-reference.md § Database Schema`

| Table | Purpose |
|---|---|
| `players` | NHL player master (id, name, team, position, date_of_birth, nhl_id). `position` is NHL.com canonical — never overwritten by other sources. |
| `player_aliases` | Name variant mapping for cross-source matching (alias_name, canonical player_id, source) |
| `player_rankings` | Per-source rank positions (player_id, source_id FK, rank, score, season, scraped_at). Retained for potential future rank-only sources; **not used by the aggregation pipeline**. |
| `player_rankings_staging` | Staging table for atomic swap pattern (same schema as player_rankings) |
| `player_stats` | Raw/actual stats per season (goals, assists, TOI, CF%, xGF%, iSCF/60, SH%, PDO, WAR, etc.). Written by NHL.com and MoneyPuck scrapers. |
| `player_trends` | ML output — `breakout_score`, `regression_risk`, `confidence`, `shap_values` JSONB, `updated_at`; UNIQUE(player_id, season) |
| `player_projections` | Per-source projected stats (source_id FK, fixed nullable stat columns for all skater/goalie stats, `extra_stats` JSONB overflow); UNIQUE(player_id, source_id, season). Written by projection source scrapers only. |
| `schedule_scores` | Off-night game counts per player per season (`off_night_games`, `total_games`, `schedule_score` 0–1 normalized); UNIQUE(player_id, season). Populated from NHL schedule API. |
| `player_platform_positions` | Platform-specific position eligibility per player (`platform`, `positions` text[]); UNIQUE(player_id, platform). Separate from `players.position`. |
| `sources` | Registered aggregation sources (name, url, scrape_config, active, last_successful_scrape, `default_weight` float, `is_paid` boolean, `user_id` nullable FK for custom user sources) |
| `scoring_configs` | Fantasy scoring presets and custom configs (stat_weights JSONB, is_preset, user_id) |
| `league_profiles` | Complete league config (user_id, name, platform, num_teams, roster_slots JSONB, scoring_config_id FK). Used for VORP computation. |
| `user_kits` | Named source-weight presets only (user_id OR session_token, source_weights JSONB, name). Not a full league config — see `league_profiles`. |
| `draft_sessions` | Live draft state (user_id, platform, league_config, picks[], available[], kit_id, status) |
| `exports` | Export job records (user_id, type, status, storage_url) |
| `subscriptions` | Stripe subscription state (user_id, stripe_session_id, plan, status, expires_at) |

---

## Data Sources & Ingestion

Scrapers run on GitHub Actions cron (daily or weekly). Each source has a dedicated scraper. Scrapers subclass either `BaseScraper` (stat sources → `player_stats`) or `BaseProjectionScraper` (projection sources → `player_projections`).

| Source | Type | Method | Frequency | Paid |
|---|---|---|---|---|
| NHL.com | Actual stats | Official API | Daily | No |
| MoneyPuck | Actual stats (advanced) | CSV downloads | Daily | No |
| Natural Stat Trick | Actual stats (advanced) | HTML scraper (BeautifulSoup) | Daily | No |
| HashtagHockey | Projections | Auto-scrape | Pre-season | No |
| DailyFaceoff | Projections | Auto-scrape | Pre-season | No |
| Apples & Ginos | Projections | Auto-scrape | Pre-season | No |
| LineupExperts | Projections | Auto-scrape | Pre-season | No |
| Yahoo | Projections | Auto-scrape / API | Pre-season | No |
| Fantrax | Projections | Auto-scrape / API | Pre-season | No |
| DatsyukToZetterberg | Projections | Paste / upload | On demand | No |
| Bangers Fantasy Hockey | Projections | Paste / upload | On demand | No |
| KUBOTA | Projections | Paste / upload | On demand | No |
| Scott Cullen | Projections | Paste / upload | On demand | No |
| Steve Laidlaw | Projections | Paste / upload | On demand | No |
| Dom Luszczyszyn | Projections | Paste / upload | On demand | Yes |

NHL.com and MoneyPuck write to `player_stats` only — they are not projection sources. Users get 2 custom projection source upload slots (CSV/Excel with column mapping UI).

**Always respect `robots.txt` and rate-limit scraper requests.**

---

## ML Trends Engine

The Trends engine has two distinct but complementary layers. Each player gets both a per-layer score and a **combined PuckLogic Trends Score** that blends them (weighted by context — pre-season vs. in-season).

---

### Layer 1 — Pre-season Breakout Model (Draft Kit)

Answers: *"Who should I draft?"*

- **Model**: XGBoost / LightGBM (gradient boosted trees — no GPU needed, fast on tabular data)
- **Label**: "breakout" = 20%+ more fantasy points than trailing 2-season avg; "regression risk" = inverse
- **Training data**: ~20 seasons (2005-06 through 2024-25; 2005-06 chosen as start year due to post-lockout rule changes making pre-lockout data structurally different) — sources: Hockey Reference, MoneyPuck CSVs, NST, NHL Edge API
- **Serving**: `joblib`-serialized model loaded at FastAPI startup; inference <10ms per player
- **Retraining**: yearly (pre-season), triggered via GitHub Action or manually
- **Explainability**: SHAP values surfaced in UI to show users *why* a player is flagged
- **Output columns** (stored in `player_trends`): `breakout_score`, `regression_risk`, `confidence`

---

### Layer 2 — In-season Leading Indicator Engine

Answers: *"Who should I pick up before anyone else notices?"*

The differentiator vs. ESPN/Yahoo last-7-days stats. Surfaces **process improvements that precede realized production** — so users act before the waiver wire runs on a player.

**Signals tracked (14-day rolling window):**

| Signal | Source | Leading edge |
|---|---|---|
| TOI change (5v5, PP, SH) | NHL.com API | More ice → more opportunity |
| PP unit movement (PP1 ↔ PP2) | Daily Faceoff / NHL.com | PP1 vs PP2 is a large fantasy multiplier |
| Shots/game trend | Natural Stat Trick, MoneyPuck | Shot volume leads goal scoring |
| xGF% shift | MoneyPuck | Chance quality improving before goals come |
| Corsi rel% shift | Natural Stat Trick | Deployment and usage improving |
| Line combo changes | Daily Faceoff | Promoted to top-6 → instant value bump |
| Shooting % vs career mean | MoneyPuck | Unlucky player due for positive regression |
| Return from injury | NHL.com injury feed | Re-insertion into a top line |

**Scoring method:**
- Compute a Z-score for each metric: `(player's 14-day rolling avg − player's season baseline) / season σ`
- Weighted sum of Z-scores → **`trending_up_score`** (0–100)
- Inverse weighting for regression signals → **`trending_down_score`**
- Both rolled into a **`momentum_score`** stored alongside pre-season scores in `player_trends`

**Celery job**: runs nightly (or after each game day) to refresh 14-day rolling stats and re-score all active players.

**Output columns added to `player_trends`**: `trending_up_score`, `trending_down_score`, `momentum_score`, `signals_json` (JSONB — per-signal Z-scores for UI explainability), `window_days` (14)

---

### Combined Score

Each player also gets a **`pucklogic_trends_score`** that blends Layer 1 + Layer 2:
- Pre-season (Aug–Sep): weighted 80% Layer 1 / 20% Layer 2 (small in-season sample)
- In-season (Oct–Apr): weighted 30% Layer 1 / 70% Layer 2
- Stored in `player_trends.pucklogic_trends_score`

---

### Monetization Gate (v2.0)

Applies to the in-season Layer 2 engine when it ships:

- **Free tier**: full Trends access except the top 10 players by `trending_up_score` (or `pucklogic_trends_score` in-season) are paywalled
- **Paid tier**: full access to all scores + `signals_json` explainability breakdown
- Gate enforced at the API layer (`/api/trends` checks subscription status; top-10 rows are stripped for free users)
- Same gate applies in the Chrome extension's Trends panel

---

## Phase Roadmap

| Phase | Period | Key Deliverables |
|---|---|---|
| 1 — Foundation | Mar–May 2026 | Turborepo scaffold, NHL.com + MoneyPuck scrapers, core DB schema, player name/ID matching, Supabase Auth, GitHub Actions cron |
| 2 — Aggregation Dashboard | Jun–Jul 2026 | Source weight UI, composite rankings table, anonymous kits, scoring config, Redis cache, Stripe, PDF/Excel exports | **Backend complete (Mar 2026).** All API routes, scrapers (Yahoo, Fantrax, NST, schedule scores, platform positions, custom upload), repositories, and tests are implemented. Frontend dashboard UI deferred. |
| 3 — ML Trends Engine (v1.0) | Aug 2026 | **Layer 1 only**: XGBoost breakout/regression model, SHAP explainability, yearly retraining, pre-season scores surfaced on rankings dashboard. **3a complete (Mar 2026)**: DB migration (`003_phase3_ml_features.sql`) + Trends API schemas (`ShapValues`, `TrendedPlayer`, `TrendsResponse`) + 26 tests. Next: 3b scraper verification + feature engineering pipeline. |
| 4 — Browser Extension | Sep–Oct 2026 | Chrome MV3 extension, ESPN + Yahoo adapters, WebSocket draft sessions, public launch (late October 2026) |
| v2.0 — In-season Trends | Post-launch | **Layer 2**: 14-day rolling Z-score engine (TOI, xGF, Corsi, PP unit, shots, line combos), nightly Celery re-scoring, combined PuckLogic Trends Score, free/paid gate (top-10 paywalled) |

---

## Testing & TDD Practices

**TDD is required.** Write the test before the implementation.

### Workflow
1. Write a failing test that defines the expected behaviour
2. Write the minimum implementation to make it pass
3. Refactor if needed, keeping tests green

### Frontend (`apps/web`) — Vitest + React Testing Library
- **Run:** `pnpm test` (single pass) · `pnpm test:watch` (watch) · `pnpm test:coverage` (with coverage)
- **Config:** `apps/web/vitest.config.ts` — jsdom env, globals enabled, v8 coverage
- **Setup:** `apps/web/src/test/setup.ts` — jest-dom matchers imported globally
- **Location:** co-locate tests in `__tests__/` next to the source file (e.g. `src/lib/api/__tests__/index.test.ts`)

### Backend (`apps/api`) — pytest + pytest-cov
- **Run:** `pytest` from `apps/api/` (coverage printed automatically)
- **Config:** `pyproject.toml` — `asyncio_mode = auto`, `testpaths = ["tests"]`, v8 coverage
- **Fixtures:** shared fixtures live in `tests/conftest.py`
- **Location:** mirror the source tree under `tests/` (e.g. `tests/repositories/test_players.py`)

### Rules
- Every new module or function must ship with tests
- Mocks over real I/O: use `vi.spyOn` / `MagicMock` — never hit real DB, HTTP, or filesystem in unit tests
- Use `TYPE_CHECKING` guards on heavy imports (e.g. `supabase.Client`) to keep the test environment portable
- All tests must be green before committing

---

## Important Notes for AI Agents

- **Phase 1 scaffold is complete.** Turborepo monorepo with Next.js (`apps/web`), FastAPI (`apps/api`), and shared UI package (`packages/ui`) are all in place. Refer to `docs/pucklogic-architecture.md` for the system overview, then `docs/backend-reference.md`, `docs/frontend-reference.md`, or `docs/extension-reference.md` for domain-specific detail. Per-phase docs are archived at `docs/archive/`.
- **Session hook**: `.claude/hooks/session-start.sh` auto-installs Node and Python deps in remote Claude Code sessions.
- **Secrets**: never commit secrets. Use `.env.local` (Next.js) and `.env` (FastAPI) — both must be gitignored.
- **Scraper ethics**: always check and respect `robots.txt`; add rate-limiting and backoff to all scrapers.
- **ESPN DOM risk**: ESPN can change their draft room UI at any time. Use multiple selector fallbacks and maintain a test fixture of the draft room HTML. Always have a manual pick-entry fallback mode.
- **Existing codebase**: treat any legacy PuckLogic code as a reference/parts bin, not a foundation. Archive as `pucklogic-legacy` before starting new build.
- **PR descriptions are mandatory**: every pull request must have a filled-out description — never leave it blank or use a placeholder. The description must include: (1) a summary of what changed and why, (2) a test plan or confirmation that existing tests cover the change, and (3) any follow-up tasks or known limitations. Update the description when additional commits are pushed to the PR (e.g. fixes from review, lint corrections).
- **Keep docs and Notion in sync**: whenever a task or feature is completed, update the relevant reference docs (`docs/`) to reflect any design changes, then update or close the corresponding Notion task card. Do this before considering the work done — docs and Notion are the source of truth for future sessions.

## MCP Tools

Always use Context7 MCP when I need library/API documentation, code generation, setup or configuration steps without me having to explicitly ask.
