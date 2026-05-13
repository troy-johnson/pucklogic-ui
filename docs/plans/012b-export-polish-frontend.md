# 012b — Export Polish Frontend Plan

**Status:** Approved  
**Date:** 2026-05-11  
**Spec:** `docs/specs/012-export-polish.md`  
**Milestone:** E — Polish exports  
**Depends on:** `docs/plans/012a-export-polish-backend.md`  
**Execution mode:** subagent dispatch  
**Wave mode:** enabled; tasks may run in parallel only within the same wave after their dependencies and protected-path gates are satisfied  

---

## Goal

Wire pre-draft workspace export actions to real XLSX/PDF browser downloads with per-action loading, success, duplicate-submit prevention, deterministic sanitized fallback filenames, and distinct action-oriented errors while preserving the existing JSON API client behavior.

## Non-Goals

- Backend export generation changes; covered by `docs/plans/012a-export-polish-backend.md`.
- CSV export.
- Native Google Sheets API integration.
- Export history/library UI.
- Yahoo, ESPN draft-room, or browser-extension export behavior.
- New entitlement, purchase, or pricing flows.

## Scope Split

This frontend plan covers Spec 012 AC1–AC6 plus frontend portions of AC14–AC15. Backend AC7–AC13 are covered by `012a-export-polish-backend`.

## File Surface

### Modified

- `apps/web/src/components/PreDraftWorkspace.tsx` — wire export actions, action state, accessible controls, success/error feedback, and duplicate-submit prevention.
- `apps/web/src/lib/api/index.ts` — add or expose a binary-response fetch path while preserving existing JSON `apiFetch` behavior.
- `apps/web/src/lib/api/__tests__/index.test.ts` — prove JSON API behavior remains unchanged and binary fetch behavior returns raw response/blob metadata.
- `apps/web/src/components/__tests__/PreDraftWorkspace.test.tsx` — export action, loading, success, duplicate-submit, and error-state coverage.
- `docs/frontend-reference.md` — canonical frontend export behavior update.

### Created

- `apps/web/src/lib/api/exports.ts` — export-specific client helper mapping UI actions to backend `excel` and `pdf`, response filename parsing, sanitized fallback filename construction, and browser download trigger.
- `apps/web/src/lib/api/__tests__/exports.test.ts` — export helper, filename, blob/download, and error mapping coverage.

### Conditional Protected Path

- `apps/web/src/app/(auth)/dashboard/page.tsx` — edit only if implementation proves `PreDraftWorkspace` lacks required kit/source/prep props. **Protected path: per-file review required before edits.**

### Deleted

- None.

## Protected Path Handling

Before editing `apps/web/src/app/(auth)/dashboard/page.tsx`, implementation must pause and present the exact prop-flow change needed. If the requested change expands auth routing, session handling, or dashboard access behavior beyond Spec 012, stop and escalate before editing.

## Implementation Tasks

### Wave 1 — RED frontend tests

1. **Wave 1 — Add binary API helper regression tests.**  
   Edit `apps/web/src/lib/api/__tests__/index.test.ts` to prove existing JSON `apiFetch` behavior remains unchanged and the new binary-response path can return response headers and blob bytes without forcing JSON parsing.  
   Command: `pnpm test -- src/lib/api/__tests__/index.test.ts` from `apps/web/`.  
   Expected output: new binary helper assertions fail before API helper implementation; existing JSON assertions continue to pass.

2. **Wave 1 — Add export client request and format-mapping tests.**  
   Create `apps/web/src/lib/api/__tests__/exports.test.ts` with tests proving Export rankings maps to backend format `excel`, Export draft sheet maps to `pdf`, the request targets `POST /exports/generate`, and auth/context payload fields are passed without CSV support.  
   Command: `pnpm test -- src/lib/api/__tests__/exports.test.ts` from `apps/web/`.  
   Expected output: tests fail because `apps/web/src/lib/api/exports.ts` does not exist yet.

3. **Wave 1 — Add export filename and download tests.**  
   Extend `apps/web/src/lib/api/__tests__/exports.test.ts` to assert `Content-Disposition` filenames are used when present and sanitized fallback filenames include `pucklogic`, kit identifier/name, export type, date, and `.xlsx` or `.pdf` extension.  
   Command: `pnpm test -- src/lib/api/__tests__/exports.test.ts` from `apps/web/`.  
   Expected output: filename/download assertions fail before helper implementation.

4. **Wave 1 — Add workspace XLSX/PDF action tests.**  
   Edit `apps/web/src/components/__tests__/PreDraftWorkspace.test.tsx` to assert authenticated users with valid active context can click Export rankings and Export draft sheet, causing the export helper to be called once for `excel` and once for `pdf`.  
   Command: `pnpm test -- src/components/__tests__/PreDraftWorkspace.test.tsx` from `apps/web/`.  
   Expected output: tests fail because visible buttons currently have no export handlers.

5. **Wave 1 — Add loading, duplicate-submit, and success tests.**  
   Extend `apps/web/src/components/__tests__/PreDraftWorkspace.test.tsx` to assert each export action shows loading while in flight, prevents duplicate submissions for that action, and shows a success affordance after the browser download is triggered.  
   Command: `pnpm test -- src/components/__tests__/PreDraftWorkspace.test.tsx` from `apps/web/`.  
   Expected output: tests fail before UI state is implemented.

6. **Wave 1 — Add distinct frontend error-state tests.**  
   Extend `apps/web/src/components/__tests__/PreDraftWorkspace.test.tsx` to assert unauthenticated, no-pass, missing-context, and generation-failure cases render distinct action-oriented messages without exposing raw entitlement implementation details.  
   Command: `pnpm test -- src/components/__tests__/PreDraftWorkspace.test.tsx` from `apps/web/`.  
   Expected output: tests fail before error mapping and rendering are implemented.

### Wave 2 — GREEN API and download helpers

7. **Wave 2 — Implement binary API response helper.**  
   Edit `apps/web/src/lib/api/index.ts` so binary export calls can receive raw response/blob data while existing JSON `apiFetch` call sites keep their current behavior.  
   Command: `pnpm test -- src/lib/api/__tests__/index.test.ts` from `apps/web/`.  
   Expected output: JSON regression tests and binary helper tests pass.

8. **Wave 2 — Implement export client helper.**  
   Create `apps/web/src/lib/api/exports.ts` with an export function that posts to `/exports/generate`, maps rankings to backend `excel`, maps draft sheet to `pdf`, parses attachment filename headers, builds sanitized fallback filenames, triggers browser download, and maps HTTP/context failures into frontend error categories.  
   Command: `pnpm test -- src/lib/api/__tests__/exports.test.ts` from `apps/web/`.  
   Expected output: export client, filename, download, and error-mapping tests pass.

### Wave 3 — GREEN workspace UI wiring

9. **Wave 3 — Wire PreDraftWorkspace export actions.**  
   Edit `apps/web/src/components/PreDraftWorkspace.tsx` so Export rankings and Export draft sheet call the export helper with the active kit/source/prep context and backend formats `excel` and `pdf`.  
   Command: `pnpm test -- src/components/__tests__/PreDraftWorkspace.test.tsx -t "Export"` from `apps/web/`.  
   Expected output: XLSX/PDF action tests pass.

10. **Wave 3 — Add per-action loading and duplicate-submit prevention.**  
    Edit `apps/web/src/components/PreDraftWorkspace.tsx` so each export action has independent in-flight state and disables duplicate submissions for the active export action.  
    Command: `pnpm test -- src/components/__tests__/PreDraftWorkspace.test.tsx -t "loading"` from `apps/web/`.  
    Expected output: loading and duplicate-submit tests pass.

11. **Wave 3 — Add success and recoverable error rendering.**  
    Edit `apps/web/src/components/PreDraftWorkspace.tsx` so successful downloads show a success affordance and unauthenticated, no-pass, missing-context, and generation-failure categories show distinct action-oriented messages.  
    Command: `pnpm test -- src/components/__tests__/PreDraftWorkspace.test.tsx -t "error"` from `apps/web/`.  
    Expected output: success and error-state tests pass without exposing raw entitlement internals.

12. **Wave 3 — Pass missing export context from dashboard only if required.**  
    If `PreDraftWorkspace` lacks required active kit/source/prep props after Tasks 9–11, pause for protected-path review, then edit `apps/web/src/app/(auth)/dashboard/page.tsx` to pass only the minimal existing context needed for export requests.  
    Command: `pnpm test -- src/app/\(auth\)/dashboard/__tests__/page.test.tsx src/components/__tests__/PreDraftWorkspace.test.tsx` from `apps/web/`.  
    Expected output: dashboard and workspace tests pass with no auth routing behavior changes.

13. **Wave 3 — Remove dead export controls.**  
    Edit `apps/web/src/components/PreDraftWorkspace.tsx` so every visible pre-draft export button is wired to a real accessible action or replaced by an equivalent accessible control.  
    Command: `pnpm test -- src/components/__tests__/PreDraftWorkspace.test.tsx` from `apps/web/`.  
    Expected output: no test fixture or accessible query finds an unwired export button.

### Wave 4 — Frontend verification and docs

14. **Wave 4 — Run focused frontend test suite.**  
    Command: `pnpm test -- src/lib/api/__tests__ src/components/__tests__` from `apps/web/`.  
    Expected output: focused API and component tests pass.

15. **Wave 4 — Run frontend lint.**  
    Command: `pnpm lint` from `apps/web/`.  
    Expected output: lint exits successfully with no frontend lint failures.

16. **Wave 4 — Update frontend reference export behavior.**  
    Edit `docs/frontend-reference.md` to document the actual pre-draft workspace export controls, `excel`/`pdf` backend format mapping, browser download behavior, loading/success/error states, and the absence of CSV or native Google Sheets API integration.  
    Command: `git diff -- docs/frontend-reference.md apps/web/src/components/PreDraftWorkspace.tsx apps/web/src/lib/api/index.ts apps/web/src/lib/api/exports.ts apps/web/src/components/__tests__/PreDraftWorkspace.test.tsx apps/web/src/lib/api/__tests__/exports.test.ts` from the repo root.  
    Expected output: diff shows canonical frontend docs aligned to implemented behavior without introducing export history, CSV, extension, or Sheets API scope.

17. **Wave 4 — Record frontend manual verification checklist.**  
    Add to the implementation summary that final validation must trigger both browser downloads from the pre-draft workspace, confirm downloaded filename extensions, open/import XLSX in spreadsheet tools, and open or print-preview the PDF.  
    Command: `git diff -- docs/frontend-reference.md` from the repo root.  
    Expected output: frontend reference or implementation notes mention manual download/file-open verification without relying on live external services in unit tests.

## Verification Mapping

| Spec AC | Frontend plan coverage |
|---|---|
| AC1 | Tasks 2, 4, 8, 9, 14 |
| AC2 | Tasks 2, 4, 8, 9, 14 |
| AC3 | Tasks 5, 10, 14 |
| AC4 | Tasks 3, 8, 14, 16 |
| AC5 | Tasks 6, 8, 11, 14, 16 |
| AC6 | Tasks 4, 9, 13, 14 |
| AC14 | Tasks 1–6 use mocked fetch/helper behavior and no live payment provider, external service, or live DB calls |
| AC15 | Tasks 14–15 run focused frontend regression tests and lint |

## Adversarial Review Record

**Decision:** required and completed before artifact write.  
**Rationale:** frontend changes touch browser downloads, API client behavior, entitlement-adjacent user messaging, and visible launch UX.  
**Disposition:** approved with revisions incorporated.

| Finding | Resolution |
|---|---|
| Backend/frontend format naming could drift between XLSX and `excel`. | Plan maps Export rankings to backend `excel` and verifies `.xlsx` download filename behavior. |
| Error categories could leak entitlement internals. | Plan maps failures into action-oriented UI messages and tests that raw internals are not exposed. |
| Binary fetch support could break JSON callers. | Plan adds regression tests for existing JSON `apiFetch` behavior before and after binary helper work. |
| Docs update could become old-doc cleanup. | Plan updates only canonical frontend reference and excludes archive or broad historical cleanup. |

## Downstream PR/QA Marker

Adversarial PR/QA review is required before ship-sync for Milestone E. The frontend review must check request format mapping, blob download behavior, filename sanitization, duplicate-submit prevention, and non-sensitive user-facing error messages.

## Risks

- Browser download tests can be brittle if they depend on real DOM URL APIs instead of mocked `URL.createObjectURL`, anchor click, and cleanup behavior.
- Existing API client code is JSON-oriented; binary support must be additive and covered by JSON regression tests.
- Missing active kit/source/prep context may require a protected dashboard prop-flow edit.

## Open Questions

- Does `PreDraftWorkspace` already receive all active kit/source/prep identifiers needed by the backend request? If not, Task 12 uses the approved protected-path process.
- Does a purchase/upgrade route already exist for no-pass errors? If not, the no-pass message should explain the requirement without linking to a non-existent route.
