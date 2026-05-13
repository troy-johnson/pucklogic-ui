# 012a — Export Polish Backend Plan

**Status:** Approved  
**Date:** 2026-05-11  
**Spec:** `docs/specs/012-export-polish.md`  
**Milestone:** E — Polish exports  
**Execution mode:** subagent dispatch  
**Wave mode:** enabled; tasks may run in parallel only within the same wave after their protected-path gates are satisfied  

---

## Goal

Make the existing backend export endpoint launch-grade for Milestone E by preserving the synchronous `POST /exports/generate` contract while locking XLSX/PDF content, deterministic attachment filenames, stable PDF context, unsupported-format rejection, and existing entitlement/source/scoring validation.

## Non-Goals

- CSV support.
- Async export jobs, object storage, generated-file persistence, or export history.
- New entitlement, purchase, pricing, or subscription models.
- Frontend download UI implementation; covered by `docs/plans/012b-export-polish-frontend.md`.

## Scope Split

This backend plan covers Spec 012 AC7–AC13 plus backend portions of AC14–AC15. Frontend AC1–AC6 are covered by `012b-export-polish-frontend` after the backend contract is stable.

## File Surface

### Modified

- `apps/api/services/exports.py` — XLSX/PDF field mapping, stable header order, PDF title/context/timestamp rendering, deterministic test seam for generation time.
- `apps/api/routers/exports.py` — attachment filename construction and response header behavior. **Protected path: per-file review required before edits.**
- `apps/api/tests/services/test_exports.py` — service-level XLSX/PDF content tests.
- `apps/api/tests/routers/test_exports.py` — route-level filename, unsupported-format, gating, ownership, paid-source, and scoring-config regression tests.
- `docs/backend-reference.md` — canonical export endpoint contract update for deterministic filenames and minimum XLSX/PDF content.

### Created

- None.

### Deleted

- None.

## Protected Path Handling

Before editing `apps/api/routers/exports.py`, implementation must pause and present the exact intended route-level changes for requester confirmation. If the requested change expands entitlement behavior or auth semantics beyond Spec 012, stop and escalate before editing.

## Implementation Tasks

### Wave 1 — RED backend tests

1. **Wave 1 — Add XLSX minimum-content service test.**  
   Edit `apps/api/tests/services/test_exports.py` to assert that generated XLSX output includes stable column order for overall rank, player name, position, team when available, computed score, fantasy/projected value when available, and league/source context.  
   Command: `pytest tests/services/test_exports.py -k "excel or xlsx"` from `apps/api/`.  
   Expected output: the new assertion fails before `apps/api/services/exports.py` is updated.

2. **Wave 1 — Add PDF printable draft-sheet service test.**  
   Edit `apps/api/tests/services/test_exports.py` to assert that generated PDF HTML/input includes a stable title/header, rank/player/position/team/score/value row content, league/profile context, and a deterministic generation timestamp.  
   Command: `pytest tests/services/test_exports.py -k "pdf"` from `apps/api/`.  
   Expected output: the new assertion fails before PDF rendering is updated.

3. **Wave 1 — Add deterministic attachment filename route test.**  
   Edit `apps/api/tests/routers/test_exports.py` to assert that XLSX/PDF responses include sanitized `Content-Disposition` filenames with app identifier, kit name or kit id fallback, export type, generation date, and `.xlsx` or `.pdf` extension.  
   Command: `pytest tests/routers/test_exports.py -k "export"` from `apps/api/`.  
   Expected output: the filename assertion fails against the current `pucklogic-rankings-{season}` style.

4. **Wave 1 — Add unsupported-format rejection regression.**  
   Edit `apps/api/tests/routers/test_exports.py` to assert that unsupported formats, including `csv`, are rejected and do not invoke export generation.  
   Command: `pytest tests/routers/test_exports.py -k "csv or unsupported or format"` from `apps/api/`.  
   Expected output: the test passes if current schema already rejects CSV, or fails only if the route currently permits an unsupported format path.

5. **Wave 1 — Add gating and validation regression assertions.**  
   Edit `apps/api/tests/routers/test_exports.py` to keep explicit coverage for kit-pass enforcement, ownership validation, paid-source validation, and scoring-config validation on export generation.  
   Command: `pytest tests/routers/test_exports.py -k "kit or pass or source or scoring or ownership"` from `apps/api/`.  
   Expected output: tests pass where existing behavior is already correct; any failure identifies a regression before implementation changes.

### Wave 2 — GREEN backend implementation

6. **Wave 2 — Update XLSX export field mapping.**  
   Edit `apps/api/services/exports.py` so XLSX generation emits the required minimum fields in stable order and includes league/source context in workbook metadata or header rows.  
   Command: `pytest tests/services/test_exports.py -k "excel or xlsx"` from `apps/api/`.  
   Expected output: the XLSX minimum-content service test passes.

7. **Wave 2 — Add deterministic PDF generation context.**  
   Edit `apps/api/services/exports.py` so PDF generation renders a printable ranked draft sheet with stable title/header, league/profile context, row content, and an injectable or freezeable generation timestamp for tests.  
   Command: `pytest tests/services/test_exports.py -k "pdf"` from `apps/api/`.  
   Expected output: the PDF service test passes without wall-clock flakiness.

8. **Wave 2 — Update export attachment filename builder.**  
   After protected-path confirmation, edit `apps/api/routers/exports.py` to build sanitized filenames containing `pucklogic`, kit name or kit id fallback, export type, generation date, and the correct extension while preserving the existing `pdf|excel` request format contract.  
   Command: `pytest tests/routers/test_exports.py -k "filename or content_disposition or export"` from `apps/api/`.  
   Expected output: filename route tests pass for both PDF and XLSX.

9. **Wave 2 — Preserve unsupported-format and gating behavior.**  
   Edit only the minimal backend code needed so CSV remains rejected and existing kit-pass, ownership, paid-source, and scoring-config validation still execute before generation.  
   Command: `pytest tests/routers/test_exports.py -k "csv or unsupported or kit or pass or source or scoring or ownership"` from `apps/api/`.  
   Expected output: all unsupported-format and validation regression tests pass.

### Wave 3 — Backend verification and docs

10. **Wave 3 — Run focused backend export test suite.**  
    Command: `pytest tests/services/test_exports.py tests/routers/test_exports.py` from `apps/api/`.  
    Expected output: all focused backend export tests pass.

11. **Wave 3 — Run backend lint.**  
    Command: `ruff check .` from `apps/api/`.  
    Expected output: ruff exits successfully with no lint failures.

12. **Wave 3 — Update backend reference export contract.**  
    Edit `docs/backend-reference.md` to document the preserved synchronous `POST /exports/generate` contract, `pdf|excel` request formats, `.pdf|.xlsx` attachment behavior, deterministic filename requirements, unsupported CSV rejection, and required minimum XLSX/PDF content.  
    Command: `git diff -- docs/backend-reference.md apps/api/services/exports.py apps/api/routers/exports.py apps/api/tests/services/test_exports.py apps/api/tests/routers/test_exports.py` from the repo root.  
    Expected output: diff shows backend docs aligned to the implemented contract without adding CSV, async jobs, storage delivery, or export history.

13. **Wave 3 — Record backend manual verification checklist.**  
    Add to the implementation summary that final validation must open the generated XLSX in an Excel-compatible tool, import/open it in Google Sheets, and open or print-preview the generated PDF.  
    Command: `git diff -- docs/backend-reference.md` from the repo root.  
    Expected output: backend reference or implementation notes mention manual file-open verification without requiring live external services in unit tests.

## Verification Mapping

| Spec AC | Backend plan coverage |
|---|---|
| AC7 | Tasks 1, 6, 10, 12 |
| AC8 | Tasks 2, 7, 10, 12 |
| AC9 | Tasks 1, 6, 10 |
| AC10 | Tasks 2, 7, 10 |
| AC11 | Tasks 4, 9, 10, 12 |
| AC12 | Tasks 5, 9, 10 |
| AC13 | Tasks 5, 9, 10 |
| AC14 | Tasks 1–5 use unit/router tests with mocked repositories/services and no live payment provider, external service, or live DB calls |
| AC15 | Tasks 10–11 run focused backend regression tests and lint |

## Adversarial Review Record

**Decision:** required and completed before artifact write.  
**Rationale:** backend changes touch export contract, generated binary content, filename semantics, and entitlement/error-adjacent routing.  
**Disposition:** approved with revisions incorporated.

| Finding | Resolution |
|---|---|
| Backend/frontend format naming could drift between XLSX and `excel`. | Plan preserves backend `pdf|excel` request format and verifies `.xlsx` attachment filename. |
| PDF timestamp tests could be flaky. | Plan requires injectable or freezeable generation timestamp. |
| Kit display name may be unavailable at route level. | Plan allows sanitized kit id fallback. |
| Error/gating work could leak entitlement internals. | Plan preserves existing backend gating and leaves user-facing category mapping to frontend plan. |
| Docs update could become old-doc cleanup. | Plan updates only canonical backend reference and excludes archive or broad historical cleanup. |

## Downstream PR/QA Marker

Adversarial PR/QA review is required before ship-sync for Milestone E. The backend review must check generated file content, deterministic filenames, unsupported-format rejection, and preservation of kit-pass/source/scoring validation.

## Risks

- WeasyPrint/openpyxl assertions can become brittle if tests inspect raw binary bytes instead of stable workbook/PDF-generation inputs.
- Filename construction may need a kit-name lookup that is not currently available; kit id fallback is the approved low-scope fallback.
- Route changes are auth/gating-adjacent and require protected-path confirmation before editing.

## Open Questions

- Does the current route already have a reliable kit display name? If not, use kit id fallback for Milestone E.
- Does the current PDF service expose an easy generation-time injection seam? If not, add a minimal optional parameter rather than a broader clock abstraction.
