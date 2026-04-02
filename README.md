# PuckLogic

Fantasy hockey draft kit built as a Turborepo monorepo.

PuckLogic combines three product surfaces:
- free rankings aggregation
- paid real-time draft monitoring via Chrome extension
- pre-season ML trends and breakout/regression analysis

## Repo Layout

```text
apps/web/            Next.js web app
apps/api/            FastAPI backend, scrapers, ML training/inference
packages/ui/         shared React UI components
packages/extension/  Chrome MV3 extension
docs/                architecture and domain reference docs
.claude/             session state and local agent workflow artifacts
```

## Start Here

If you are new to the repo, read these in order:

1. `AGENTS.md` - agent-neutral repo orientation and doc precedence
2. `.agents/axon-state.md` - current phase, active focus, and next steps
3. `docs/pucklogic-architecture.md` - system overview and canonical product architecture
4. One or more domain references, depending on the task:
   - `docs/backend-reference.md`
   - `docs/frontend-reference.md`
   - `docs/extension-reference.md`

## Canonical Docs

These documents are the current implementation source of truth:

- `docs/pucklogic-architecture.md`
- `docs/backend-reference.md`
- `docs/frontend-reference.md`
- `docs/extension-reference.md`
- current milestone specs and plans in `docs/superpowers/`

Historical material in `docs/archive/` is reference-only unless a current doc explicitly points back to it.

## Development Commands

From repo root:

```bash
pnpm install
pnpm run dev
pnpm run build
pnpm run lint
pnpm run test
```

Backend:

```bash
cd apps/api
pip install -e ".[dev]"
uvicorn main:app --reload
pytest
ruff check .
```

Frontend:

```bash
cd apps/web
pnpm run dev
pnpm test
```

## Workflow Notes

- Current task and phase tracking lives in `.agents/axon-state.md`.
- `CLAUDE.md` contains Claude-specific workflow guidance.
- `AGENTS.md` is the neutral entrypoint for Codex and other coding agents.
- Keep docs and task tracking in sync when a milestone closes.

## Product Scope Snapshot

- v1.0 target: rankings aggregator + paid draft monitor
- ML trends engine ships as pre-season Layer 1 scores
- v2.0 adds in-season Layer 2 trends

For detailed scope and architecture, use `docs/pucklogic-architecture.md` instead of inferring from historical docs.
