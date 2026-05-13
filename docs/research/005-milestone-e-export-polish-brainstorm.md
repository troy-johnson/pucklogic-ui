# Milestone E Export Polish Brainstorm

**Date:** 2026-05-10  
**Status:** Brainstorm recommendation for spec drafting  
**Recommended next artifact:** `docs/specs/012-export-polish.md`

## Context

Milestone E is the next launch milestone after Milestone D. Current workflow state identifies it as **export polish**, with scope still undefined. Current roadmap language says **“E — Polish exports.”** The older `008a` draft-season readiness plan labels the same area as **“Make exports launch-grade”** and lists spreadsheet readability, Excel/Google Sheets compatibility, correct ranking/fantasy-point fields, and printable/downloadable flow usability.

Current backend documentation already defines a synchronous `POST /exports/generate` endpoint that returns XLSX or PDF bytes and requires a kit pass. Current frontend documentation says `ExportPanel` should call this endpoint synchronously. Milestone D delivered visible export buttons in the pre-draft workspace, but available discovery found no frontend API wiring from those buttons to `/exports/generate`.

## User Decision

CSV export is **out of scope** for Milestone E. The milestone should stay limited to the already documented **XLSX + PDF** formats.

## Goals

- Make the existing XLSX/PDF export flow usable from the pre-draft workspace.
- Preserve auth, prep, source, and kit-pass gating.
- Improve export content and presentation enough that downloads are useful during draft preparation and live draft reference.
- Verify output compatibility with Excel, Google Sheets import, and browser download behavior where practical.
- Keep the export pipeline synchronous unless implementation evidence proves that impossible for launch-scale payloads.

## Non-Goals

- CSV export.
- Async export jobs, queues, or storage-backed generated files.
- Yahoo-specific or extension-specific behavior.
- Major backend export architecture changes.
- New monetization or entitlement model changes beyond preserving existing kit-pass gating.

## Approaches Considered

### Option A — Minimal launch polish

Wire the existing XLSX/PDF backend endpoint to the frontend buttons, add browser download handling, and expose loading/error states.

**Pros**
- Fastest path to a working launch flow.
- Low architectural risk.
- Uses existing backend contract.

**Cons**
- May leave spreadsheet/PDF structure rough.
- Does not fully satisfy the “launch-grade” language from the readiness plan.
- Compatibility confidence may remain limited.

### Option B — Launch-grade export quality pass

Wire the frontend buttons and improve XLSX/PDF content structure, field coverage, file naming, readability, and compatibility tests.

**Pros**
- Best match for documented Milestone E intent.
- Keeps scope bounded to existing formats and synchronous endpoint.
- Converts visible Milestone D buttons into a real paid/gated user flow.
- Creates clearer acceptance criteria for implementation and validation.

**Cons**
- Larger than a pure wiring task.
- Requires careful definition of which fields and formatting are launch-critical.
- May need targeted backend and frontend test coverage.

### Option C — Export platform expansion

Add CSV, async jobs, saved export history, storage-backed files, or richer format selection.

**Pros**
- More flexible long-term export foundation.
- Could serve future integrations.

**Cons**
- Scope creep relative to current milestone language.
- CSV is explicitly out of scope by user decision.
- Async/storage architecture is not currently documented as needed.
- Higher implementation and verification risk before launch.

## Recommendation

Proceed with **Option B — Launch-grade export quality pass**.

Milestone E should be defined as:

> Make the existing XLSX/PDF export flow gated, downloadable, readable, and verified from the pre-draft workspace.

The spec should focus on a concrete contract:

- Two export actions in the pre-draft workspace: rankings spreadsheet and printable draft sheet.
- Existing backend formats only: XLSX and PDF.
- Browser download handling with deterministic filenames.
- Clear loading, success, and recoverable error states.
- Backend output includes ranking, player identity, position/team, projected/fantasy-point fields, and draft-useful notes/tiers where already available.
- XLSX output is readable with frozen/header rows and sensible column widths if supported by current library usage.
- PDF output is printable and legible for draft-room use.
- Gating failures produce actionable frontend messaging without leaking entitlement details.

## Assumptions

- The current `POST /exports/generate` endpoint remains the backend export authority.
- Existing entitlement checks are correct and should be preserved, not redesigned.
- Export input can be derived from the current pre-draft kit/source context.
- Launch-scale export generation remains safe as a synchronous request.
- Google Sheets compatibility means import/readability of XLSX, not native Sheets API integration.

## Risks

- Current backend export tests may validate file generation but not real spreadsheet readability or PDF layout quality.
- Frontend wiring may need API-client and blob-download utilities that were not part of Milestone D.
- If export payloads are unexpectedly large, synchronous generation could create slow requests; this should be measured but not preemptively redesigned.
- Existing docs mention an `ExportPanel`, while the implemented UI may currently expose export buttons inside `PreDraftWorkspace`; spec should name behavior, not overfit to component names.

## Open Questions for Spec

1. Which exact fields are mandatory in the XLSX rankings export?
2. Is the PDF draft sheet a full ranked list, a condensed cheat sheet, or both?
3. What browser support level is required for downloads at launch?
4. Should failed entitlement/prep/source checks show a generic export error or route the user to purchase/prep completion?
5. Should export events be logged for product analytics now, or deferred?

## Spec Handoff

Draft `docs/specs/012-export-polish.md` next. Keep the spec narrow: XLSX + PDF only, synchronous export only, pre-draft workspace only, launch-grade usability and verification.
