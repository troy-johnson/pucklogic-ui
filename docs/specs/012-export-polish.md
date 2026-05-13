# 012 — Export Polish

**Status:** Approved — adversarial review round 1 complete; pre-plan gate met  
**Date:** 2026-05-10  
**Milestone:** E — Polish exports  
**Related research:** `docs/research/005-milestone-e-export-polish-brainstorm.md`  
**Related specs:** `docs/specs/009-web-draft-kit-ux.md`, `docs/specs/010-web-ui-wireframes-design.md`, `docs/specs/011-milestone-c-token-pass-backend.md`  
**Related docs:** `docs/backend-reference.md`, `docs/frontend-reference.md`

---

## Summary

Milestone E makes the existing export flow launch-grade. Users working in the pre-draft workspace must be able to generate and download the already documented XLSX and PDF exports through the visible export actions delivered in Milestone D. The exported files must be gated, deterministic, readable, and useful for draft preparation or draft-room reference.

This milestone does not create a broader export platform. It preserves the current synchronous `POST /exports/generate` contract and limits supported formats to XLSX and PDF.

## Goals

- Wire pre-draft workspace export actions to real XLSX/PDF downloads.
- Preserve existing auth, kit/source, prep, and kit-pass gating.
- Make exported rankings and draft sheets readable enough for launch use in spreadsheet and print workflows.
- Include a documented minimum field set so users can draft from the file without returning to the app for basic context.
- Provide clear loading, success, and recoverable error states in the frontend.
- Verify backend file generation and frontend browser-download behavior with automated tests where practical.

## Non-Goals

- CSV export.
- Async export jobs, queues, generated-file persistence, or object-storage delivery.
- Native Google Sheets API integration.
- Yahoo, ESPN draft-room, or browser-extension export behavior.
- New entitlement, purchase, or pricing model changes.
- A separate export history/library UI.
- Analytics instrumentation unless it already exists and can be reused without expanding scope.

## Current State

- Backend documentation defines `POST /exports/generate` as a synchronous export endpoint returning XLSX or PDF bytes.
- Backend export generation already exists for XLSX and PDF and is kit-pass gated.
- Frontend documentation expects export UI to call the synchronous endpoint.
- Milestone D surfaced export buttons in the pre-draft workspace, but discovery found no confirmed frontend API wiring to `/exports/generate`.
- Historical readiness notes define Milestone E as making exports launch-grade through spreadsheet structure, readability, compatibility, correct fields, and printable/downloadable usability.

## User-Facing Contract

### Export actions

The pre-draft workspace exposes two launch export actions:

1. **Export rankings** — downloads an XLSX spreadsheet for sorting/filtering in Excel-compatible tools.
2. **Export draft sheet** — downloads a PDF draft sheet intended for print or second-screen draft-room reference.

Both actions use the active kit/source context from the current pre-draft workspace. If required context is missing, the user sees an actionable error instead of a broken download.

### Supported formats

| User action | Required format | Notes |
|---|---|---|
| Export rankings | XLSX | Must open readably in Excel-compatible spreadsheet tools and import readably into Google Sheets. |
| Export draft sheet | PDF | Must be printable/legible as a compact draft-room reference. |

CSV is not supported in Milestone E. Google Sheets compatibility means XLSX import/readability, not native Google Sheets API integration.

### Required export content

Each export must include enough context to identify and use ranked players during a draft.

#### XLSX minimum fields

- Overall rank.
- Player name.
- Position.
- Team when available.
- PuckLogic score or equivalent computed ranking score.
- Fantasy points or projected fantasy value when available from the current ranking result.
- Source/ranking context needed to understand the row, such as league profile or source-weight summary in workbook metadata/header rows.
- Tier, notes, or source-specific rank columns only when already available in the current ranking data model.

#### PDF minimum fields

- Overall rank.
- Player name.
- Position.
- Team when available.
- PuckLogic score or equivalent computed ranking score.
- Fantasy points or projected fantasy value when available.
- League/profile context and generation timestamp in a header or footer.

The PDF is a printable ranked draft sheet. A more advanced condensed cheat sheet with custom grouping is out of scope unless it falls out naturally from existing export code.

### File naming

Downloaded files must use deterministic, human-readable names that include:

- Product or app identifier.
- Active kit name or safe fallback identifier.
- Export type.
- Date of generation.
- Correct extension: `.xlsx` or `.pdf`.

Names must be sanitized for common filesystem restrictions.

### Frontend states

For each export action, the UI must expose:

- Idle state with enabled action when export prerequisites are met.
- Loading state while generation/download is in progress.
- Success affordance after the browser download has been triggered.
- Recoverable error state when the request fails.

Error messages must be action-oriented and must not leak sensitive entitlement internals.

Required error categories:

- Unauthenticated user: prompt sign-in or account creation.
- Authenticated user without required kit pass: explain that export requires a kit pass and route toward purchase/upgrade if such route exists.
- Missing or invalid kit/source/prep context: direct the user to complete or recompute the kit.
- Backend generation failure: explain that export failed and offer retry.

## Design Decisions

| ID | Decision | Rationale | Alternatives rejected |
|---|---|---|---|
| D1 | Milestone E supports XLSX and PDF only. | These are already documented and implemented backend formats; user selected XLSX/PDF-only for the CSV scope question. | CSV as required format; CSV as hidden implementation task. |
| D2 | Keep export generation synchronous for this milestone. | Current backend and frontend docs define synchronous bytes response; launch polish should avoid queue/storage architecture. | Async jobs, stored generated files, export history. |
| D3 | Exports are launched from the pre-draft workspace. | Spec 009 and Milestone D UI place export/print in the pre-draft flow. | Separate export page or library. |
| D4 | PDF is a printable ranked draft sheet, not a new cheat-sheet product. | Keeps scope aligned to launch usability while avoiding layout/product expansion. | Full custom cheat-sheet builder; multiple PDF templates. |
| D5 | Compatibility means readable XLSX import/open behavior, not third-party API integration. | Historical notes mention Excel/Google Sheets compatibility; native Sheets integration would be new product scope. | Google Sheets API export; CSV as Sheets workaround. |

## Acceptance Criteria

### Frontend behavior

- AC1: From the authenticated pre-draft workspace, a user with valid kit/source context and required entitlement can trigger **Export rankings** and receive a browser download request for an `.xlsx` file.
- AC2: From the authenticated pre-draft workspace, a user with valid kit/source context and required entitlement can trigger **Export draft sheet** and receive a browser download request for a `.pdf` file.
- AC3: Each export action shows a loading state while the request is in flight and prevents duplicate submissions for that action.
- AC4: Successful export requests produce deterministic sanitized filenames containing app identifier, kit identifier/name, export type, date, and correct extension.
- AC5: Unauthenticated, no-pass, missing-context, and generation-failure cases render distinct action-oriented messages without exposing internal entitlement implementation details.
- AC6: Existing visible export buttons are either wired directly or replaced with equivalent accessible controls; no dead export buttons remain in the pre-draft workspace.

### Backend/export content

- AC7: XLSX exports include the required minimum fields: rank, player name, position, team when available, computed score, fantasy/projected value when available, and league/source context.
- AC8: PDF exports include the required minimum fields: rank, player name, position, team when available, computed score, fantasy/projected value when available, league/profile context, and generation timestamp.
- AC9: XLSX output has a readable header row and stable column order covered by tests.
- AC10: PDF output is generated with a stable title/header and row content covered by tests.
- AC11: Unsupported export formats, including CSV, remain rejected by the backend contract.

### Gating and regressions

- AC12: Existing kit-pass gating remains enforced for export generation.
- AC13: Existing ownership/paid-source/scoring-config validation remains enforced for export generation.
- AC14: Unit tests do not call real external services, real payment providers, or live databases.
- AC15: Existing backend export tests and frontend workspace tests continue to pass after the change.

## Verification Expectations

Implementation should include focused automated coverage for:

- Backend XLSX field/header generation.
- Backend PDF field/header generation.
- Backend rejection of unsupported formats such as CSV.
- Frontend export API call construction.
- Frontend blob download handling and filename sanitization.
- Frontend loading, success, and error states for both export actions.

Manual or documented verification should cover:

- Opening the XLSX in an Excel-compatible tool.
- Importing/opening the XLSX in Google Sheets.
- Opening and printing, or print-previewing, the PDF draft sheet.

## Resolved Questions

| Question | Resolution |
|---|---|
| Should CSV be part of Milestone E? | No. Milestone E remains XLSX + PDF only. |
| Should export generation become async/storage-backed? | No. Preserve synchronous bytes response for launch. |
| Where should users start exports? | The pre-draft workspace. |
| Does Google Sheets compatibility require Sheets API integration? | No. It means readable XLSX import/open behavior. |
| Is PDF a full cheat-sheet builder? | No. It is a printable ranked draft sheet with required minimum fields. |

## Open Questions for Planning

1. Which current frontend component should own export state: existing `PreDraftWorkspace`, a new `ExportPanel`, or a small extracted export-actions component?
2. What exact request payload does the current frontend kit/source state need to send to `POST /exports/generate`?
3. Does the backend already expose enough ranking fields for AC7/AC8, or does the export service need a small mapping update?
4. What purchase/upgrade route currently exists for no-pass errors, if any?

## ADR Signal Review

No standalone ADR is required. The spec intentionally preserves existing export architecture: synchronous generation, XLSX/PDF formats, and pre-draft workspace placement. Decisions D1–D5 constrain Milestone E scope but do not introduce a new long-term system abstraction.

## Adversarial Review Record

**Packet path:** `docs/specs/012-export-polish-adversarial-review-r1.md`  
**Round:** 1  
**Date:** 2026-05-10  
**Verdict:** `APPROVED WITH NITS`

### Findings addressed

| ID | Resolution |
|---|---|
| F-1 | Added explicit XLSX/PDF minimum field sets. |
| F-2 | Defined PDF as printable ranked draft sheet, not full cheat-sheet builder. |
| F-3 | Clarified Google Sheets compatibility as XLSX import/readability only. |
| F-4 | Added required non-sensitive, action-oriented error categories. |

### Pre-plan gate

Met. Planning may proceed.

## Self-Review

- Placeholder scan complete: no placeholder markers remain.
- Scope check complete: CSV, async jobs, storage, export history, extension/Yahoo work, and entitlement redesign are excluded.
- Ambiguity check complete: minimum export fields, supported formats, frontend states, and gating behavior are specified.
- Internal consistency check complete: acceptance criteria align with goals and non-goals.
