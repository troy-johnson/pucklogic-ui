# PuckLogic Draft Kit — Claude Code Context

## Project Overview

PuckLogic is a fantasy hockey draft kit targeting casual and competitive/keeper players. It consists of two products: a **free rankings aggregator** (users select sources, assign weights, get a custom consensus ranking) and a **paid real-time draft monitor** delivered as a Chrome browser extension. A secondary **Trends engine** layers ML-powered breakout/regression predictions on top of the rankings. Target launch: September 2026 (before the 2026–27 NHL season).

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
| `player_trends` | ML output (breakout_score, regression_risk, confidence, updated_at) |
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

- **Model**: XGBoost / LightGBM (gradient boosted trees — no GPU needed, fast on tabular data)
- **Label**: "breakout" = 20%+ more fantasy points than trailing 2-season avg; "regression risk" = inverse
- **Training data**: 10+ NHL seasons (Hockey Reference, MoneyPuck CSVs, NST, NHL Edge API)
- **Serving**: `joblib`-serialized model loaded at FastAPI startup; inference <10ms per player
- **Retraining**: yearly (pre-season), triggered via GitHub Action or manually
- **Explainability**: SHAP values surfaced in UI to show users *why* a player is flagged

---

## Phase Roadmap

| Phase | Period | Key Deliverables |
|---|---|---|
| 1 — Foundation | Mar–Apr 2026 | Turborepo scaffold, NHL.com + MoneyPuck scrapers, core DB schema, Supabase Auth, GitHub Actions cron |
| 2 — Aggregation Dashboard | May–Jun 2026 | Source weight UI, composite rankings table, Redis cache, Stripe, PDF/Excel exports |
| 3 — ML Trends Engine | Jul 2026 | XGBoost model, SHAP explainability, nightly re-scoring Celery job |
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
