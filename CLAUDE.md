# PuckLogic Draft Kit — Claude Code Context

## Project Overview

PuckLogic is a fantasy hockey draft kit targeting casual and competitive/keeper players.

**v1.0 (target: September 2026)** — two products:
1. **Free rankings aggregator**: users select sources, assign weights, get a custom consensus ranking
2. **Paid real-time draft monitor**: Chrome browser extension with live best-available suggestions

The Trends engine (Layer 1 only) ships in v1.0 as pre-season breakout/regression scores overlaid on the rankings.

**v2.0 (post-launch)** — in-season leading indicator engine (Layer 2): 14-day rolling Z-scores for TOI, xGF%, Corsi, PP unit changes, line combos, etc. Surfaces players trending up *before* production shows up in standard stats.

Full architecture details: `pucklogic_architecture.docx`

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
.claude/
  hooks/        # Claude Code session start hook
  settings.json
pucklogic_architecture.docx
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
- **Rankings algorithm**: per-source rank → normalize to 0–1 score → user-defined weights → weighted average → sort descending. Missing sources degrade gracefully (weight redistributed). Results cached in Redis for 6h.
- **Draft monitor**: `MutationObserver` watches ESPN Fantasy DOM for pick events → service worker relays via WebSocket to backend → backend returns best-available suggestions.
- **Paywalled sources** (Dom Luszczyszyn / The Athletic): user paste UI (CSV/text) at launch; pursue data agreement in 2027.
- **Extension monetization**: $2–3 one-time per draft session; payment via Stripe on the web app — no payment UI in the extension itself (simplifies Chrome Web Store compliance).

---

## Core Database Tables (Supabase PostgreSQL)

| Table | Purpose |
|---|---|
| `players` | NHL player master (id, name, team, position, dob, nhl_id) |
| `player_rankings` | Per-source rankings (player_id, source, rank, score, season, scraped_at) |
| `player_stats` | Raw stats per season (goals, assists, TOI, CF%, xGF%, etc.) |
| `player_trends` | ML output — Layer 1: `breakout_score`, `regression_risk`, `confidence`; Layer 2: `trending_up_score`, `trending_down_score`, `momentum_score`, `signals_json`, `window_days`; Combined: `pucklogic_trends_score`, `updated_at` |
| `sources` | Registered aggregation sources (name, url, scrape_config, active) |
| `user_kits` | Saved user weighting configs (user_id, weights JSON, name) |
| `draft_sessions` | Live draft state (user_id, league_config, picks[], available[]) |
| `exports` | Export job records (user_id, type, status, storage_url) |
| `subscriptions` | Stripe subscription state (user_id, plan, expires_at) |

---

## Data Sources & Ingestion

Scrapers run on GitHub Actions cron (daily or weekly). Each source has a dedicated scraper.

| Source | Method | Frequency |
|---|---|---|
| NHL.com | Official API | Daily |
| MoneyPuck | CSV downloads | Daily |
| Natural Stat Trick | HTML scraper (BeautifulSoup) | Daily |
| Dobber Hockey | HTML scraper (may need Playwright) | Weekly |
| Dom Luszczyszyn | User paste UI | On demand |
| Elite Prospects | HTML scraper or EP API | Weekly |

**Always respect `robots.txt` and rate-limit scraper requests.**

---

## ML Trends Engine

The Trends engine has two distinct but complementary layers. Each player gets both a per-layer score and a **combined PuckLogic Trends Score** that blends them (weighted by context — pre-season vs. in-season).

---

### Layer 1 — Pre-season Breakout Model (Draft Kit)

Answers: *"Who should I draft?"*

- **Model**: XGBoost / LightGBM (gradient boosted trees — no GPU needed, fast on tabular data)
- **Label**: "breakout" = 20%+ more fantasy points than trailing 2-season avg; "regression risk" = inverse
- **Training data**: 10+ NHL seasons (Hockey Reference, MoneyPuck CSVs, NST, NHL Edge API)
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
| 1 — Foundation | Mar–Apr 2026 | Turborepo scaffold, NHL.com + MoneyPuck scrapers, core DB schema, Supabase Auth, GitHub Actions cron |
| 2 — Aggregation Dashboard | May–Jun 2026 | Source weight UI, composite rankings table, Redis cache, Stripe, PDF/Excel exports |
| 3 — ML Trends Engine (v1.0) | Jul 2026 | **Layer 1 only**: XGBoost breakout/regression model, SHAP explainability, yearly retraining, pre-season scores surfaced on rankings dashboard |
| v2.0 — In-season Trends | Post-launch | **Layer 2**: 14-day rolling Z-score engine (TOI, xGF, Corsi, PP unit, shots, line combos), nightly Celery re-scoring, combined PuckLogic Trends Score, free/paid gate (top-10 paywalled) |
| 4 — Browser Extension | Aug–Sep 2026 | Chrome MV3 extension, ESPN DOM observer, WebSocket draft sessions, public launch |

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

- **Phase 1 scaffold is complete.** Turborepo monorepo with Next.js (`apps/web`), FastAPI (`apps/api`), and shared UI package (`packages/ui`) are all in place. Refer to `pucklogic_architecture.docx` for full design rationale.
- **Session hook**: `.claude/hooks/session-start.sh` auto-installs Node and Python deps in remote Claude Code sessions.
- **Secrets**: never commit secrets. Use `.env.local` (Next.js) and `.env` (FastAPI) — both must be gitignored.
- **Scraper ethics**: always check and respect `robots.txt`; add rate-limiting and backoff to all scrapers.
- **ESPN DOM risk**: ESPN can change their draft room UI at any time. Use multiple selector fallbacks and maintain a test fixture of the draft room HTML. Always have a manual pick-entry fallback mode.
- **Existing codebase**: treat any legacy PuckLogic code as a reference/parts bin, not a foundation. Archive as `pucklogic-legacy` before starting new build.
