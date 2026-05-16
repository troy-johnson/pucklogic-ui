# Adversarial PR/QA Review — Milestone E Export Polish

**Artifact type:** Implementation review  
**Spec:** `docs/specs/012-export-polish.md`  
**Plans:** `docs/plans/012a-export-polish-backend.md`, `docs/plans/012b-export-polish-frontend.md`  
**Round number:** 1 (updated with remediation verification)
**Reviewer lens:** Spec compliance, end-to-end wiring, entitlement gating, test coverage evidence  
**Required verdict set:** `APPROVED`, `APPROVED WITH NITS`, `HOLD`  
**Review date:** 2026-05-13

---

## Files Reviewed

- `apps/api/services/exports.py`
- `apps/api/routers/exports.py`
- `apps/api/tests/services/test_exports.py`
- `apps/api/tests/routers/test_exports.py`
- `apps/web/src/lib/api/exports.ts`
- `apps/web/src/lib/api/index.ts`
- `apps/web/src/components/PreDraftWorkspace.tsx`
- `apps/web/src/components/__tests__/PreDraftWorkspace.test.tsx`
- `apps/web/src/lib/api/__tests__/exports.test.ts`
- `apps/web/src/app/(auth)/dashboard/page.tsx`
- `apps/web/src/lib/rankings/load-initial.ts`
- `apps/web/src/app/(auth)/dashboard/__tests__/page.test.tsx`

---

## Stage 1 — Spec Compliance

| AC | Status | Evidence |
|---|---|---|
| AC1 | PASS | Dashboard now passes `exportContext` (`token`, `season`, `scoringConfigId`, `platform`) into `PreDraftWorkspace`; export handlers call `downloadExport` with required request context. |
| AC2 | PASS | Same as AC1; draft-sheet path now receives required context from dashboard wiring. |
| AC3 | PASS | Per-action `exporting === type` guard disables duplicate submissions; button label changes during flight. Tested. |
| AC4 | PASS | Deterministic sanitized filenames built from scoring_config_id + export type + date + extension. Tested in router and export client. |
| AC5 | PASS | Four distinct action-oriented messages: sign-in prompt, kit-pass message, recompute prompt, retry guidance. Raw entitlement internals not exposed. Tested. |
| AC6 | PASS | Dashboard wiring now enables both buttons to execute real export requests rather than immediate `missing-context` errors. |
| AC7 | PASS | `generate_excel` now accepts `context_label`; workbook subject includes concrete scoring config + source summary + league profile context passed from route. |
| AC8 | PASS | `generate_pdf` now accepts `context_label`; printable header includes concrete context label instead of generic fallback. |
| AC9 | PASS | Stable column order asserted in `test_header_row_base_columns` and `test_launch_xlsx_minimum_columns_and_context_metadata`. |
| AC10 | PASS | Stable PDF title, header context, and row content tested in `test_printable_draft_sheet_header_context_and_timestamp`. |
| AC11 | PASS | CSV and unsupported format types return 422 without invoking generation. Tested in `TestExportValidation`. |
| AC12 | PASS | `require_kit_pass` dependency enforces kit-pass gating before generation. 403 path tested in `TestKitPassGating`. |
| AC13 | PASS | Source ownership, paid-source, and scoring-config validation enforced and tested in `TestExportAccessValidation`. |
| AC14 | PASS | All tests use mocks/stubs; no real DB, payment provider, or external service calls. |
| AC15 | PASS | Verified by direct test runs: backend export router/service tests pass; frontend dashboard/export tests pass. |

**Stage 1 verdict: PASS**

---

## Stage 2 — Code Quality

### Blockers

No open blockers.

Resolved blockers:

- **B-1 resolved** (`apps/web/src/app/(auth)/dashboard/page.tsx`, `apps/web/src/lib/rankings/load-initial.ts`, `apps/web/src/app/(auth)/dashboard/__tests__/page.test.tsx`)
  - Dashboard now constructs and passes `exportContext` from server-loaded ranking context.
  - Test coverage verifies `PreDraftWorkspace` receives the expected export context payload.

- **B-2 resolved** (`apps/api/routers/exports.py`, `apps/api/services/exports.py`, `apps/api/tests/routers/test_exports.py`, `apps/api/tests/services/test_exports.py`)
  - Route now builds a concrete `context_label` (scoring config + league profile + source weights).
  - `generate_excel` and `generate_pdf` receive and render context label.
  - Tests verify route passes label and generated artifacts include label.

- **B-3 resolved**
  - Backend run: `pytest apps/api/tests/routers/test_exports.py apps/api/tests/services/test_exports.py` → **62 passed**.
  - Frontend run: `pnpm --filter web test -- src/app/(auth)/dashboard/__tests__/page.test.tsx src/components/__tests__/PreDraftWorkspace.test.tsx` (workspace run output included) → **27 files / 202 tests passed**.

### Important

**I-1: No-pass category detection relies on backend message string**  
`categoryForApiError` in `exports.ts` routes 403 to `no-pass` only when `error.message.toLowerCase().includes("kit pass")`. The backend sends `"detail": "kit pass required"` which satisfies this today, but message-format drift breaks the category mapping silently. Other 403 responses (e.g., paid-source authorization) would fall through to `generation-failed` rather than `no-pass`, which is correct behavior, but the detection is fragile.

Fix (optional, post-ship acceptable): Document this coupling in a comment or use a response header/code rather than message content inspection.

### Minor

**M-1: Content-Disposition filename parsing is narrow**  
`filenameFromResponse` regex `/filename="?([^";]+)"?/i` handles simple `filename=` and `filename="..."` variants but not RFC 5987 `filename*=UTF-8''...` encoding. Backend generates ASCII-safe names so this is not a current regression risk, but the parser will silently fall back to the client-generated filename if the backend ever uses extended encoding.

**M-2: Fallback filename date uses client clock**  
`fallbackFilename` constructs dates with `new Date().toISOString().slice(0, 10)` (client local time). Backend filenames use UTC. A one-day drift is possible for users in UTC+ zones near midnight when the backend response omits a `Content-Disposition` header.

**M-3: Column label semantics**  
"PuckLogic Score" (column 5) is populated with `projected_fantasy_points`; "Projected Fantasy Value" (column 6) is populated with `vorp`. These mappings are internally consistent and tested, but VORP is a relative differential (value over replacement), not an absolute fantasy projection. The labeling may confuse users who expect "Projected Fantasy Value" to be a raw points projection. Not a spec AC violation given the "or equivalent" language, but warrants a naming review post-launch.

---

## Ship Gate Assessment

| Gate requirement | Status |
|---|---|
| Adversarial PR/QA review | This document |
| AC1–AC6 frontend behavior | PASS |
| AC7–AC10 backend content | PASS |
| AC11–AC13 gating/regressions | PASS |
| AC14 no live-service calls | PASS |
| AC15 existing tests pass | PASS |

**Ship gate: CLEAR**

---

## Verdict

`APPROVED WITH NITS`

All previously identified blockers (B-1, B-2, B-3) are resolved and validated by tests.

Remaining nits (I-1, M-1, M-2, M-3) are non-blocking for Milestone E ship-sync and should be tracked for post-launch hardening/UX clarity.

---

## Remediation Delta (2026-05-13)

This packet was updated after implementation fixes landed. Net result:

- AC status moved from FAIL/PARTIAL to PASS for AC1, AC2, AC6, AC7, AC8.
- AC15 moved from unverified to PASS with direct command evidence.
- Final disposition changed from `HOLD` to `APPROVED WITH NITS`.
