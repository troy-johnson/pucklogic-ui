# Plan: Optional pick_number in Auto-Ingestion Path

**Spec basis:** `docs/specs/008-live-draft-sync-launch-required.md`  
**Depends on:** `008c` merged to `main`  
**Risk Tier:** 2 — Backend service logic change with test coverage requirement  
**Scope:** Small (~half day)  
**Execution mode:** Sequential steps

---

## Problem

`parsePickNumber` in `packages/extension/src/content/shared.ts` returns `0` when the pick number cannot be parsed from the DOM. The extension then forwards `pick_number: 0` to the backend, which rejects any `pick_number < 1` and silently drops the pick (the error response is also dropped since `onmessage` is unassigned on the bridge socket). The result is a silent data-loss path on the primary pick-forwarding route.

## Goal

Make `pick_number` optional in the WebSocket auto-ingestion path. When the extension cannot parse a pick number from the DOM, it omits the field. The backend derives the sequence position from session state (`last_processed_pick + 1`) and accepts the pick. The manual HTTP endpoint keeps `pick_number` required.

## Non-Goals

- Changing the manual-pick HTTP endpoint contract
- Wiring `onmessage` on the background bridge (separate follow-up)
- Changing the sequential ordering check when `pick_number` is explicitly provided

---

## Key Tradeoff

When `pick_number` is auto-derived, the backend trusts its own cursor rather than the extension's observed value. A stale DOM mutation that fires twice produces two accepted picks (one with the correct player name, one potentially stale). This is acceptable for the auto-ingestion path because the backend is the session authority, and the extension's pick number is unreliable anyway when selectors partially match.

---

## File Surface

| File | Change |
|---|---|
| `apps/api/services/draft_sessions.py` | `accept_pick` signature: `pick_number: int | None`; auto-derive when `None` |
| `apps/api/routers/draft_sessions.py` | WS handler: treat missing/invalid `pick_number` as `None` instead of rejecting |
| `apps/api/tests/services/test_draft_sessions.py` | Add `accept_pick(pick_number=None)` coverage |
| `apps/api/tests/routers/test_draft_sessions.py` | Add WS pick-without-pick_number coverage |
| `packages/extension/src/content/shared.ts` | `parsePickNumber` returns `number \| undefined`; return `undefined` instead of `0` |
| `packages/extension/src/__tests__/espn.test.ts` | Update pick extraction assertions expecting `pickNumber: undefined` |
| `packages/extension/src/__tests__/protocol.test.ts` | Update `isPickPayload` tests if affected |
| `docs/specs/008-live-draft-sync-launch-required.md` | Mark `pick_number` optional in `pick` event table for auto-ingestion |
| `docs/extension-reference.md` | Same annotation in protocol surface section |

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
raw = payload.get("pick_number")
pick_number: int | None = raw if isinstance(raw, int) and raw >= 1 else None
```

Pass `pick_number` to `service.accept_pick`. In the `state_update` response, read the resolved pick number from `result["accepted_pick"]["pick_number"]` instead of the raw payload value.

### Step 3 — Backend tests

Add to service tests:
- `accept_pick(pick_number=None)` on a fresh session produces `pick_number=1`
- Sequential `accept_pick(pick_number=None)` calls advance the cursor correctly

Add to router WS tests:
- `pick` event without `pick_number` field is accepted and produces `state_update`
- `pick` event with `pick_number: 0` is accepted (treated as absent)
- `pick` event with an explicit out-of-turn `pick_number` still raises

### Step 4 — Extension: `parsePickNumber`

Change return type from `number` to `number | undefined`. Return `undefined` instead of `0` when no digit is found or input is null.

Update `DetectedPick.pickNumber` to `number | undefined`.

`JSON.stringify` drops `undefined` values, so omitting `pick_number` from the payload happens automatically — no change needed in the content scripts or background bridge.

### Step 5 — Extension tests

Update any test assertions that expected `pickNumber: 0` to expect `pickNumber: undefined`. Confirm `isPickPayload` still accepts payloads without `pick_number`.

### Step 6 — Spec and docs

In `docs/specs/008-live-draft-sync-launch-required.md`, update the `pick` event table:

| Field | Required | Notes |
|---|---|---|
| `player_name` | Yes | |
| `pick_number` | No (auto-ingestion) | Backend derives from session cursor when absent. Required for manual-pick HTTP endpoint. |

Apply the same annotation to the protocol surface section of `docs/extension-reference.md`.

---

## Acceptance Criteria

- [ ] `pnpm --filter @pucklogic/extension test` passes with `pickNumber: undefined` throughout
- [ ] `pytest apps/api/tests/services/test_draft_sessions.py` passes with `pick_number=None` cases
- [ ] `pytest apps/api/tests/routers/test_draft_sessions.py` passes with no-pick-number WS cases
- [ ] A pick event sent without `pick_number` is accepted by the backend and produces a correct `state_update` response
- [ ] A pick event sent with `pick_number: 0` is accepted (treated as absent, not rejected)
- [ ] A pick event with an explicit out-of-turn `pick_number` still produces an error response
- [ ] Manual-pick HTTP endpoint contract is unchanged
