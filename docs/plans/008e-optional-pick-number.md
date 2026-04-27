# Plan: Optional pick_number in Auto-Ingestion Path

**Spec basis:** `docs/specs/008-live-draft-sync-launch-required.md`  
**Depends on:** `008c` merged to `main` — **verified: PR #33 merged**  
**Risk Tier:** 2 — Backend service logic change with test coverage requirement  
**Scope:** Small (~half day)  
**Execution mode:** Sequential steps

---

## Problem

`parsePickNumber` in `packages/extension/src/content/shared.ts` returns `0` when the pick number cannot be parsed from the DOM. The extension then forwards `pick_number: 0` to the backend, which rejects any `pick_number < 1` and silently drops the pick (the error response is also dropped since `onmessage` is unassigned on the bridge socket). The result is a silent data-loss path on the primary pick-forwarding route.

## Goal

Make `pick_number` optional in the WebSocket auto-ingestion path. When the extension cannot parse a pick number from the DOM, it omits the field. The backend derives the sequence position from session state (`last_processed_pick + 1`) and accepts the pick. The manual HTTP endpoint keeps `pick_number` required.

## Non-Goals

- Changing the manual-pick HTTP endpoint contract (it remains strict: `pick_number` required)
- Wiring `onmessage` on the background bridge (separate follow-up)
- Changing the sequential ordering check when `pick_number` is explicitly provided
- Redesigning the extension protocol validator — `isPickPayload` in `shared/protocol.ts` already accepts omitted `pick_number` (`pick_number?: number`); no changes needed there

---

## Normalization Rule (explicit)

| WS payload `pick_number` | Backend treatment |
|---|---|
| Absent (field omitted) | Derive: `(last_processed_pick or 0) + 1`; skip ordering check |
| `0`, negative, non-integer, boolean, string | Treat as absent — same derivation path |
| Positive integer `>= 1` | Keep existing in-turn / out-of-turn ordering checks |

The router normalization expression: `raw if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 1 else None`.

**Observability:** Malformed values (0, negative, wrong type) are silently treated as absent — no log or metric emitted. DOM-miss is expected and frequent; logging it would produce noise in production. If future observability is needed, it belongs in the extension-side `selector_fallback` signal, not in the backend normalizer.

---

## Key Tradeoff

When `pick_number` is auto-derived, the backend trusts its own cursor rather than the extension's observed value. A stale DOM mutation that fires twice produces two accepted picks (one with the correct player name, one potentially stale). This is acceptable for the auto-ingestion path because the backend is the session authority, and the extension's pick number is unreliable anyway when selectors partially match.

---

## File Surface

| File | Change |
|---|---|
| `apps/api/services/draft_sessions.py` | `accept_pick` signature: `pick_number: int \| None`; auto-derive when `None` |
| `apps/api/routers/draft_sessions.py` | WS handler: normalize missing/invalid `pick_number` to `None`; read `state_update.pick_number` from result |
| `apps/api/tests/services/test_draft_sessions.py` | Add `accept_pick(pick_number=None)` coverage |
| `apps/api/tests/routers/test_draft_sessions.py` | Add WS pick-without-pick_number and pick-with-zero cases; add manual-HTTP strict regression |
| `packages/extension/src/content/shared.ts` | `parsePickNumber` returns `number \| undefined`; return `undefined` instead of `0`; update `DetectedPick.pickNumber` to `number \| undefined` |
| `packages/extension/src/content/yahoo.ts` | Type-follows from `DetectedPick` change; `lastPickNumber` already `number \| undefined` — verify no explicit `0` comparison |
| `packages/extension/src/__tests__/espn.test.ts` | Add test: DOM-miss path → `parsePickNumber` returns `undefined` → payload omits `pick_number` |
| `packages/extension/src/__tests__/yahoo.test.ts` | Add test: DOM-miss path → `pickNumber` is `undefined` |
| `packages/extension/src/__tests__/background.test.ts` | Add test: `PICK_DETECTED` with `pickNumber: undefined` → `pick_number` absent from serialized JSON |
| `docs/specs/008-live-draft-sync-launch-required.md` | Update "Pick event minimum fields" section: annotate `pick_number` as optional for auto-ingestion |
| `docs/extension-reference.md` | Update "Shared parsing" section (`parsePickNumber`, `DetectedPick`): annotate return type + omission behavior |

**Not in scope:**
- `packages/extension/src/shared/protocol.ts` — `isPickPayload` already allows omitted `pick_number`; no changes needed
- `packages/extension/src/__tests__/protocol.test.ts` — existing test already asserts `isPickPayload({ player_name: "..." }) === true`

---

## Steps

### Step 1 — Service layer

In `accept_pick`, change `pick_number: int` to `pick_number: int | None`.

When `None`, derive: `pick_number = (last_processed_pick or 0) + 1` and skip the sequential ordering check. When provided, keep existing `< expected` / `> expected` guards unchanged.

The resolved `pick_number` (derived or explicit) is used for all downstream writes: `accepted_pick["pick_number"]`, `last_processed_pick`, and `cursor`.

### Step 2 — Router WS handler

Replace:
```python
pick_number = payload.get("pick_number")
if not isinstance(pick_number, int) or pick_number < 1:
    await websocket.send_json({"type": "error", ...})
    continue
```

With:
```python
raw_payload = message.get("payload")
payload = raw_payload if isinstance(raw_payload, dict) else {}
raw = payload.get("pick_number")
pick_number: int | None = (
    raw if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 1 else None
)
```

The `isinstance(raw_payload, dict)` guard is a real bug fix: the current `message.get("payload") or {}` passes `{}` for `None`/empty but would `AttributeError` on a list or string payload, since `.get()` is not defined on those types.

Pass `pick_number` to `service.accept_pick`. In the `state_update` response, read the resolved pick number from `result["accepted_pick"]["pick_number"]` instead of the raw payload value (the raw value may be `None` when derived).

### Step 3 — Backend tests

Add to service tests:
- `accept_pick(pick_number=None)` on a fresh session produces `pick_number=1`
- Sequential `accept_pick(pick_number=None)` calls advance the cursor correctly

Add to router WS tests:
- `pick` event without `pick_number` field is accepted and produces `state_update`
- `pick` event with `pick_number: 0` is accepted (treated as absent)
- `pick` event with an explicit out-of-turn `pick_number` still produces an error response
- `state_update.payload.pick_number` reflects the backend-resolved value (not the raw payload value)
- `pick` event with a non-dict `payload` (e.g. `payload: []` or `payload: "bad"`) is accepted without a server error — treated as absent `pick_number`

Add to router HTTP tests (regression):
- Manual-pick endpoint still rejects requests missing `pick_number` — confirm strict contract is unchanged

### Step 4 — Extension: `parsePickNumber`

Change return type from `number` to `number | undefined`. Return `undefined` instead of `0` when no digit is found or input is null/empty.

Update `DetectedPick.pickNumber` to `number | undefined`.

`JSON.stringify` drops `undefined` values, so omitting `pick_number` from the WS payload happens automatically — no change needed in the content scripts or background bridge send path.

### Step 5 — Extension tests

**No existing `pickNumber: 0` assertions need updating** — all current pick-number test fixtures use valid positive integers.

Add direct unit tests for `parsePickNumber` to `espn.test.ts` (or a new `shared.test.ts`):
- `parsePickNumber(null)` → `undefined`
- `parsePickNumber("")` → `undefined`
- `parsePickNumber("no digits here")` → `undefined`
- `parsePickNumber("Pick 7")` → `7` (regression — still works for valid input)

Add to `espn.test.ts`:
- DOM-miss: pick container present but no pick-number element → `parsePickNumber` returns `undefined` → `sendPickMessage` called with `pickNumber: undefined`

Add to `yahoo.test.ts`:
- Same DOM-miss case for Yahoo path

Add to `background.test.ts`:
- `PICK_DETECTED` with `pickNumber: undefined` → the serialized JSON payload does not contain `pick_number` key

Confirm `isPickPayload` behavior is unchanged — no edits to `protocol.ts` or `protocol.test.ts`.

### Step 6 — Spec and docs

In `docs/specs/008-live-draft-sync-launch-required.md`, under the "Pick event minimum fields" section, annotate `pick_number`:

> `pick_number` — optional for auto-ingestion (WS path). Backend derives from session cursor when absent or when value is not a positive integer. Required for the manual-pick HTTP endpoint.

In `docs/extension-reference.md`, under the "Shared parsing (`src/content/shared.ts`)" section, update `parsePickNumber` and `DetectedPick`:

> `parsePickNumber(text)` — returns `number | undefined`; returns `undefined` when text is null, empty, or contains no digit sequence  
> `DetectedPick.pickNumber` — `number | undefined`; `undefined` when pick number cannot be parsed from DOM

---

## Acceptance Criteria

- [ ] `pnpm --filter @pucklogic/extension test` passes with `pickNumber: undefined` throughout
- [ ] `pytest apps/api/tests/services/test_draft_sessions.py` passes with `pick_number=None` cases
- [ ] `pytest apps/api/tests/routers/test_draft_sessions.py` passes with no-pick-number and pick-number-zero WS cases
- [ ] A pick event sent without `pick_number` is accepted by the backend and produces a correct `state_update` response
- [ ] A pick event sent with `pick_number: 0` is accepted (treated as absent, not rejected)
- [ ] `state_update.payload.pick_number` reflects the backend-resolved (derived or explicit) value
- [ ] A pick event with an explicit out-of-turn `pick_number` still produces an error response
- [ ] Manual-pick HTTP endpoint contract is unchanged — still requires a positive integer `pick_number`
- [ ] `PICK_DETECTED` with `pickNumber: undefined` serializes without a `pick_number` key in the WS JSON
- [ ] `pick` event with a non-dict `payload` (array or string) does not cause a server error
- [ ] `parsePickNumber(null)`, `parsePickNumber("")`, and `parsePickNumber("no digits")` all return `undefined`
