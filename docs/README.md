# Documentation map

- `adrs/` — architectural and design decision records
- `specs/` — active product specs awaiting implementation
- `plans/` — execution plans for approved specs
- `research/` — research notes and findings for active investigations
- `archive/` — historical docs and retired references

Active feature adrs, specs, plans, and research live under `docs/`. Legacy phase-specific artifacts remain in `archive/`.

Canonical reference docs live at the top level:
- `backend-reference.md`
- `frontend-reference.md`
- `extension-reference.md`
- `specs/feature-engineering-spec.md`
- `pucklogic-architecture.md`

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
   - top-level canonical references / architecture docs
   - `adrs/`
   - `specs/`
   - `plans/`
   - `research/`
   - `archive/`

Rules:

- If a spec says it **supersedes** another doc for a particular concern, follow the newer spec for that concern even if the older doc remains relevant for adjacent constraints.
- If two docs appear to conflict and neither explicitly supersedes the other, prefer the top-level reference or ADR and flag the conflict instead of guessing.
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
