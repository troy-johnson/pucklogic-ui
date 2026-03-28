# AGENTS.md

Use this file as the repo entrypoint for any coding agent.

## Read Order

1. `.claude/SESSION_STATE.md` - current phase, branch context, open PR state, next steps
2. `AGENTS.md` - doc precedence, repo conventions, operating notes
3. `docs/pucklogic-architecture.md` - canonical system overview
4. Domain docs relevant to the task:
   - `docs/backend-reference.md`
   - `docs/frontend-reference.md`
   - `docs/extension-reference.md`
5. Current milestone specs/plans in `docs/superpowers/` when working inside an active feature area

## Source Of Truth

Treat these as canonical unless a newer current doc explicitly replaces them:

- `docs/pucklogic-architecture.md`
- `docs/backend-reference.md`
- `docs/frontend-reference.md`
- `docs/extension-reference.md`
- active milestone specs and plans in `docs/superpowers/`

Do not treat `docs/archive/` as canonical implementation guidance. Archive docs are historical context only.

## Repo Conventions

- Monorepo: Turborepo
- Frontend: Next.js App Router in `apps/web/`
- Backend: FastAPI in `apps/api/`
- Shared UI: `packages/ui/`
- Extension: `packages/extension/`
- TDD is expected for implementation work

## Workflow Expectations

- Check `.claude/SESSION_STATE.md` before assuming the active phase or next task.
- Prefer existing canonical docs over older summary/reference docs.
- `CLAUDE.md` is Claude-specific workflow guidance. It may be useful context, but non-Claude agents should not rely on it as the sole onboarding document.
- Keep new documentation navigational when possible; avoid creating large duplicate reference docs.

## Branch And Commit Safety

- Do not commit directly to `main`.
- Create a feature branch for implementation or significant doc work.
- Do not revert unrelated local changes you did not make.
- Run relevant tests or verification steps before claiming work is complete.

## Documentation Rules

- Prefer updating the canonical doc rather than creating a parallel explanation.
- If a doc is only a summary, say so explicitly and link to the canonical contract.
- If historical material is still useful, keep it under `docs/archive/` and label it as non-canonical.

## Operational Notes

- Supabase is currently operated on the free tier with a single project; do not assume a separate staging/test environment exists.
- Secrets live in local env files and must never be committed.
- Use current code and current docs together; if they disagree, flag the conflict instead of guessing.
