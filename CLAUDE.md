# PuckLogic Draft Kit — Claude Code Context

## Context Guardrails

These rules apply in every session, before any other instruction.

1. **Session state:** Read `.claude/SESSION_STATE.md` as the first action of every session. If it does not exist, say so and ask the user what to work on. Do not assume phase or branch from memory.

2. **Phase verification:** Before implementing anything, confirm which phase is active from `SESSION_STATE.md` and `docs/pucklogic-architecture.md`. If the user's request references a phase that does not match, ask for clarification.

3. **Branch integrity:** You are prohibited from committing to `main`. Always run `git branch --show-current` before any `git commit` or `git push`. If on `main`, stop and create a feature branch first.

4. **Context refresh:** If a session exceeds 20 messages without a commit or clear milestone, proactively overwrite `.claude/SESSION_STATE.md` with current progress and ask the user if they want to continue or start fresh.

5. **Stale context signal:** If you find yourself uncertain about the current phase, branch, or PR number — run `/sync` rather than guessing.

---

## Development Workflow

**MANDATORY:** When starting any new feature, milestone, or task, invoke the `feature-dev` skill. This covers the full cycle: context loading → brainstorm → plan → branch → implement (TDD) → verify → code review → PR → external review → sync.

The skill reads project-specific configuration from `.claude/feature-dev/config.md` (commands, directories, enabled agents, prompt paths). Do not wait for the user to ask for individual steps — the skill defines when each step is required.

---

## Project Overview

PuckLogic is a fantasy hockey draft kit. **v1.0 (target: late October 2026):**
1. Free rankings aggregator (source weights, composite ranking)
2. Paid real-time draft monitor (Chrome extension, live suggestions)

**v2.0 (post-launch):** In-season Layer 2 Trends engine (14-day rolling Z-scores).

Full details: `docs/pucklogic-architecture.md`, `docs/backend-reference.md`, `docs/feature-engineering-spec.md`

---

## Tech Stack

| Layer | Technology |
|---|---|
| Monorepo | Turborepo |
| Frontend | Next.js 14+ (App Router), Tailwind CSS, shadcn/ui, Zustand, SWR |
| Backend | FastAPI (Python), Celery + Redis |
| Database | Supabase (PostgreSQL + Auth + Storage) |
| Cache | Upstash Redis (6h TTL) |
| ML / Trends | XGBoost / LightGBM, scikit-learn, SHAP, joblib |
| Browser Extension | Chrome MV3, React (`packages/ui`) |
| Exports | WeasyPrint (PDF), openpyxl (Excel) |
| Payments | Stripe Checkout |
| Hosting | Vercel (frontend), Railway or Fly.io (backend) |

---

## Monorepo Structure

```
apps/web/          # Next.js 14+ frontend
apps/api/          # FastAPI backend + ML inference
packages/ui/       # Shared React components
packages/extension/ # Chrome MV3 extension
docs/              # Architecture, backend, frontend, extension reference
.claude/           # Hooks, session state, skills
```

---

## Dev Commands

**Repo root:** `pnpm install` · `pnpm run dev` · `pnpm run build` · `pnpm run lint` · `pnpm run test`

**Backend:**
```bash
cd apps/api
pip install -e ".[dev]"
uvicorn main:app --reload   # http://localhost:8000
pytest && ruff check .
```

**Frontend:** `cd apps/web && pnpm run dev`  (http://localhost:3000)

---

## Phase Roadmap

| Phase | Status | Key Deliverables |
|---|---|---|
| 1 — Foundation | Complete | Turborepo scaffold, scrapers, DB schema, Supabase Auth |
| 2 — Aggregation | Backend complete (Mar 2026) | Rankings API, scoring config, Redis cache, Stripe, exports. Frontend UI deferred. |
| 3 — ML Trends (v1.0) | 3a + 3b complete; 3c next | XGBoost breakout model, SHAP, yearly retraining. 3a: schema migration + API schemas. 3b: smoke tests + scraper fixes. |
| 4 — Browser Extension | Sep–Oct 2026 | Chrome MV3, ESPN/Yahoo adapters, WebSocket sessions |
| v2.0 — In-season Trends | Post-launch | Layer 2: 14-day Z-scores, nightly Celery re-scoring |

---

## Testing & TDD

**TDD is required.** Write the test before the implementation.

**Backend (`apps/api`):** `pytest` · fixtures in `tests/conftest.py` · mirror source tree under `tests/`

**Frontend (`apps/web`):** `pnpm test` · Vitest + RTL · co-locate tests in `__tests__/`

**Rules:** Every new function ships with tests. Use mocks (`MagicMock`, `vi.spyOn`) — never hit real DB/HTTP in unit tests. All tests green before committing.

---

## Important Notes

- **Secrets:** Never commit. Use `.env.local` (Next.js) and `.env` (FastAPI) — both gitignored.
- **Scraper ethics:** Always respect `robots.txt`; add rate-limiting and backoff.
- **ESPN DOM risk:** ESPN can change their draft room UI. Use multiple selector fallbacks + manual pick-entry fallback mode.
- **PR descriptions are mandatory:** Summary of changes + test plan + known limitations. Update when new commits are pushed.
- **Keep docs and Notion in sync:** Update `docs/` and close the Notion card before considering any task done.

## MCP Tools

Always use Context7 MCP when I need library/API documentation, code generation, setup or configuration steps without me having to explicitly ask.
