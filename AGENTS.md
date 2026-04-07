# AGENTS.md

Use this file as the repo entrypoint for any coding agent.

## Read Order

1. `.agents/axon-state.md` - current phase, branch context, open PR state, next steps
2. `AGENTS.md` - doc precedence, repo conventions, operating notes
3. `docs/pucklogic-architecture.md` - canonical system overview
4. Domain docs relevant to the task:
   - `docs/backend-reference.md`
   - `docs/frontend-reference.md`
   - `docs/extension-reference.md`
5. Current milestone specs in `docs/specs/` and plans in `docs/plans/` when working inside an active feature area

## Source Of Truth

Treat these as canonical unless a newer current doc explicitly replaces them:

- `docs/pucklogic-architecture.md`
- `docs/backend-reference.md`
- `docs/frontend-reference.md`
- `docs/extension-reference.md`
- active milestone specs in `docs/specs/` and plans in `docs/plans/`

Do not treat `docs/archive/` as canonical implementation guidance. Archive docs are historical context only.

## Repo Conventions

- Monorepo: Turborepo
- Frontend: Next.js App Router in `apps/web/`
- Backend: FastAPI in `apps/api/`
- Shared UI: `packages/ui/`
- Extension: `packages/extension/`
- TDD is expected for implementation work

## Workflow Expectations

- Check `.agents/axon-state.md` before assuming the active phase or next task.
- Prefer existing canonical docs over older summary/reference docs.
- Use the `axon` / `axon:develop` workflow for new feature or milestone work.
- `CLAUDE.md` is only a thin pointer to `AGENTS.md` and should not carry repo policy.
- Keep new documentation navigational when possible; avoid creating large duplicate reference docs.

## TDD / Test Rules

- TDD is expected for implementation work: write the test before the implementation.
- Every new function should ship with tests.
- Use mocks/stubs for unit tests; do not hit real DB/HTTP in unit tests.
- Run relevant tests and verification before claiming a task is complete.

## PR Hygiene

- PR descriptions are mandatory.
- Include a summary of changes, a test plan, and known limitations.
- Update the PR description when new commits are pushed or scope changes.

## Scraper / ESPN Guardrails

- Always respect `robots.txt`; add rate limiting and backoff where needed.
- ESPN draft-room DOM can change; use multiple selector fallbacks and a manual pick-entry fallback mode.
- Prefer safe, incremental scraper changes over broad rewrites.

## Status Sync Hierarchy

- **Notion is the overarching project-status source of truth.** Update the relevant Notion page/card first when project state changes.
- **`.agents/axon-state.md` is the operational session tracker.** Reconcile it to Notion after any meaningful status change.
- **Serena memories are durable reference notes.** Update them when the project gains a long-lived fact or convention that future sessions should inherit.
- Before merge/review handoff, ensure Notion, axon-state, and Serena do not conflict on the current phase, blockers, and next steps.
- Keep `.claude/SESSION_STATE.md` current locally if used, but do not commit it.

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
