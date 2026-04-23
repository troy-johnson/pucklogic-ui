# Documentation map

Top-level docs answer different questions and should stay distinct:

- `ROADMAP.md` — time-phased execution view: milestone status, launch sequencing, cut rules, and major blocked/follow-up work
- `pucklogic-architecture.md` — system blueprint: product shape, stack, data model, hosting, and cross-surface architecture
- `backend-reference.md` — backend implementation reference: schema, API routes, security, pipelines, and backend conventions
- `frontend-reference.md` — web implementation reference: app structure, auth, state, UI/data flow, and frontend conventions
- `extension-reference.md` — extension implementation reference: MV3 runtime, adapters, transport, fallback, and extension conventions

Structured doc folders under `docs/` hold the evolving delivery artifacts:

- `adrs/` — architectural and design decision records
- `specs/` — active product specs awaiting or guiding implementation
- `plans/` — execution plans for approved specs
- `research/` — research notes and findings for active investigations
- `archive/` — historical docs and retired references

Active feature ADRs, specs, plans, and research live under `docs/`. Legacy phase-specific artifacts remain in `archive/`.

## Which doc to update

Use this quick guide before editing docs:

- **Update `ROADMAP.md`** when milestone timing, sequencing, launch priority, cut rules, or cross-cutting blocked work changes.
- **Update `pucklogic-architecture.md`** when the overall system design, hosting model, data architecture, or cross-surface responsibilities change.
- **Update a surface reference doc** when the canonical behavior or implementation contract for that surface changes.
  - `backend-reference.md` for backend routes, schema, security, ingestion, and export behavior
  - `frontend-reference.md` for web app structure, state, and UX implementation contracts
  - `extension-reference.md` for extension runtime, adapter, protocol, and fallback behavior
- **Update an ADR** when a durable technical or product-architecture decision is made.
- **Update a spec** when the product contract or acceptance criteria change.
- **Update a plan** when implementation sequencing, readiness, or execution status changes.
- **Update `.agents/axon-state.md`** when the current branch, active phase, blockers, or next steps change for the active session.

## Notion vs repo docs

Use Notion and repo docs for different jobs:

- **Notion** is the broader project-management layer:
  - task tracking
  - project status coordination
  - higher-level planning and execution follow-through
- **`docs/ROADMAP.md`** is the repo-visible milestone sequencing and launch-prioritization layer.
- **Repo docs** (`pucklogic-architecture.md`, reference docs, ADRs, specs, and plans) are the canonical source for technical behavior, implementation contracts, and accepted design decisions.
- **`.agents/axon-state.md`** is the operational session tracker for the current branch, active phase, blockers, and next steps.

Rules:

- If Notion and repo docs disagree on **technical behavior or implementation contract**, the canonical repo docs win.
- If Notion and repo docs disagree on **current project/task status**, reconcile Notion, `docs/ROADMAP.md`, and `.agents/axon-state.md` so they do not drift.
- Do not use Notion to silently replace or override specs, ADRs, plans, architecture docs, or surface reference docs.

## Agent instructions for documentation updates

When an agent changes meaningful project state, implementation scope, or canonical behavior, it must decide whether updates are needed in both the repo docs and Notion.

### Always check whether these need updating

- **Repo docs**
  - `docs/ROADMAP.md` for milestone sequencing, blocked work, and launch-priority changes
  - `docs/pucklogic-architecture.md` for cross-system architecture changes
  - `docs/backend-reference.md`, `docs/frontend-reference.md`, `docs/extension-reference.md` for surface-level canonical behavior changes
  - relevant `docs/specs/*.md` if acceptance criteria or product contract changed
  - relevant `docs/plans/*.md` if execution status, readiness, or sequencing changed
  - `.agents/axon-state.md` for the active branch, current phase, blockers, and next steps
- **Notion**
  - project/task cards when implementation status, blockers, launch posture, or follow-up work changed
  - roadmap/project tracking when repo-visible milestone state changed enough that Notion would otherwise drift

### Required agent behavior

Agents working in this repo should follow this checklist before ending a meaningful implementation or documentation session:

1. **Update canonical repo docs first** when technical behavior, architecture, specs, plans, or references changed.
2. **Update `.agents/axon-state.md`** to capture the current operational truth for the next session.
3. **Reconcile Notion** when project/task status, blockers, or launch posture changed.
4. **Check for conflicts** across Notion, `docs/ROADMAP.md`, and `.agents/axon-state.md`.
5. **Do not leave stale status behind** in one system after updating another.

### Minimum sync expectations by change type

- **Technical contract changed** → update repo canonical docs; update Notion only if project/task state is affected.
- **Implementation status changed** → update plan/status docs, `.agents/axon-state.md`, and the relevant Notion task/project cards.
- **Blocked/deferred/pre-launch follow-up discovered** → update `docs/ROADMAP.md`, relevant plan/reference docs, and the relevant Notion task/project entries.
- **Roadmap or milestone status changed** → update `docs/ROADMAP.md`, relevant Notion project/task views, and `.agents/axon-state.md` if it affects active work.

## Documentation classification policy

Use the document type to decide where a file belongs:

- **ADR**: durable architecture or system-behavior decision; answers *how the system should work*
- **Spec**: current product or feature contract; answers *what we are building*
- **Plan**: execution sequencing for an approved spec; answers *how we intend to deliver it*
- **Research**: exploratory notes, brainstorms, source analysis, and supporting rationale that are informative but not themselves canonical contracts
- **Archive**: superseded, historical, or retired material kept only for context

## Canonical and recency policy

When multiple docs cover similar subject matter, use this precedence order:

1. A doc explicitly marked as **canonical**, **source of truth**, or **reference**
2. A newer numbered artifact that explicitly **supersedes** an older one
3. The folder type, in this order for implementation decisions:
   - `ROADMAP.md` for milestone sequencing and launch prioritization only
   - top-level canonical references / architecture docs for system and surface behavior
   - `adrs/`
   - `specs/`
   - `plans/`
   - `research/`
   - `archive/`

Rules:

- If a spec says it **supersedes** another doc for a particular concern, follow the newer spec for that concern even if the older doc remains relevant for adjacent constraints.
- If two docs appear to conflict and neither explicitly supersedes the other, prefer the top-level reference or ADR and flag the conflict instead of guessing.
- `ROADMAP.md` is a planning/status layer. It should not silently override architecture docs, reference docs, specs, or ADRs on behavioral details.
- Research docs explain **why** decisions were made, but they do not override specs, ADRs, or canonical references.
- Plans track execution status, but they do not replace the spec or ADR they reference.

## Numbering policy

- Numbering is sequential **within each folder class** (`adrs`, `specs`, `plans`, `research`).
- Existing numbered docs are treated as **stable IDs** once published; do not renumber historical docs casually.
- New docs should take the next available number in that folder.
- The folder `INDEX.md` files are the authoritative guides for sequence, date, and current status.
- Draft plan revisions may use suffixes like `d1`, `d2`, etc. beneath the parent plan identifier.

## Continuity policy

- When meaningful documentation state changes, update `.agents/axon-state.md` so future sessions inherit the correct branch, current focus, and next steps.
- If documentation taxonomy or canonical-source rules change, reflect that in both `docs/README.md` and `.agents/axon-state.md` before ending the session.
