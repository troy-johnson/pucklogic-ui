# Adversarial Review Packet — Spec 012 Export Polish

**Artifact type:** Spec  
**Artifact path:** `docs/specs/012-export-polish.md`  
**Originating research:** `docs/research/005-milestone-e-export-polish-brainstorm.md`  
**Round number:** 1  
**Reviewer lens:** Launch readiness, scope control, implementation ambiguity, entitlement/error-surface risk  
**Required verdict set:** `APPROVED`, `APPROVED WITH NITS`, `CHANGES REQUIRED`

## Key Claims Under Review

1. Milestone E is export polish, not a broader export-platform rebuild.
2. CSV, async jobs, storage-backed exports, Yahoo/extension behavior, and entitlement model changes are out of scope.
3. Existing XLSX/PDF backend generation remains the export authority.
4. Pre-draft workspace export buttons must become real gated download actions.
5. Acceptance criteria are specific enough for a TDD implementation plan.

## Evidence Sources

- `docs/state/workflow-state.md` — Milestone E next; export polish scope currently undefined.
- `docs/ROADMAP.md` — Milestone E named as “Polish exports.”
- `docs/plans/008a-draft-season-readiness.md` — historical/reference language: “Make exports launch-grade.”
- `docs/backend-reference.md` — current contract: synchronous `POST /exports/generate` for XLSX/PDF bytes, kit-pass gated.
- `docs/frontend-reference.md` — current expectation: frontend export panel calls synchronous export endpoint.
- `docs/research/005-milestone-e-export-polish-brainstorm.md` — selected Option B and user decision to exclude CSV.

## Findings

| ID | Severity | Finding | Required correction |
|---|---|---|---|
| F-1 | Important | “Correct fields” can become ambiguous unless the spec lists mandatory minimum fields. | Add explicit minimum field set for XLSX/PDF export content. |
| F-2 | Important | PDF draft sheet shape could drift between full ranked list and condensed cheat sheet. | Define PDF as printable draft sheet with ranked rows and compact field set; richer cheat-sheet grouping may be deferred. |
| F-3 | Minor | “Google Sheets compatibility” can imply API integration. | State that compatibility means XLSX import/readability, not native Sheets integration. |
| F-4 | Minor | Error handling can leak entitlement internals or be too generic to recover. | Require action-oriented, non-sensitive error states for unauthenticated, no-pass, missing-kit, and generation-failed cases. |

## Verdict

`APPROVED WITH NITS`

The spec may proceed if F-1 through F-4 are reflected in the artifact before planning. No council or ADR is required because the spec preserves the existing synchronous XLSX/PDF export architecture rather than creating a new long-term export abstraction.

## Findings Resolution

**Reviewed:** 2026-05-10  
**Reviewer:** orchestration  
**Status:** All findings addressed — pre-plan gate met

| ID | Original finding | Resolution in spec |
|---|---|---|
| F-1 | "Correct fields" ambiguous without a mandatory minimum field list. | Added explicit XLSX minimum fields (rank, name, position, team, score, fantasy value, source context) and PDF minimum fields (same core set plus generation timestamp) under "Required export content." |
| F-2 | PDF draft sheet shape could drift between full ranked list and condensed cheat sheet. | PDF defined as "printable ranked draft sheet" with required minimum fields; cheat-sheet grouping explicitly deferred in non-goals and in D4. |
| F-3 | "Google Sheets compatibility" could imply native Sheets API integration. | Clarified in supported-formats table and D5: compatibility means readable XLSX import/open behavior, not Google Sheets API integration. |
| F-4 | Error states could leak entitlement internals or be too generic to recover from. | Four required error categories added (unauthenticated, no-pass, missing context, generation failure), each with action-oriented, non-sensitive messaging requirement. Covered by AC5. |

Planning may proceed.
