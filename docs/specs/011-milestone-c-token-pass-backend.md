# Spec 011 — Milestone C Token / Pass Backend

| | |
|---|---|
| **Status** | Approved |
| **Date** | 2026-04-29 |
| **Window** | Milestone C, 2026-05-05 → 2026-05-18 |
| **Predecessors** | 008 (live-draft sync), 008d (draft-pass session lifecycle), 009 (web draft kit UX) |
| **Successors** | Spec 010 / 010a UI work consumes the read surface and gating contracts defined here |

## Summary

Milestone C delivers the launch entitlement backend: kit-pass schema, kit-pass Stripe SKU and webhook crediting, a unified `/entitlements` read surface for web and extension, kit-pass gating on customization and export endpoints, and a rankings snapshot written into `draft_sessions` at session close for the post-season ML comparison job. This spec also closes a stale documentation conflict by codifying the launch decision: no separate `draft_tokens` or `entitlements` table is introduced; entitlements live on the existing `subscriptions` row.

## Decision Record — Launch Entitlement Model

The ROADMAP previously called for designing and implementing a `draft_tokens` table. That bullet predates 008d and is stale. As of 008d, draft passes are stored as an integer counter on the existing `subscriptions` row (`draft_pass_balance`) with three database helpers (`consume_draft_pass`, `restore_draft_pass`, `credit_draft_pass_for_stripe_event`), guarded by a `subscriptions_user_id_unique` index and the `stripe_processed_events` table.

**Launch decision (canonical):** Both draft passes and kit pass live on the single `subscriptions` row per user. **No `draft_tokens` table. No generic `entitlements` table.** Future multi-pass or multi-product entitlements (bundles, refunds, gift codes, downgrades) remain explicitly out of scope for launch; if and when they ship, they may justify revisiting the table layout, but they will be designed in their own spec.

**Doc reconciliation as part of this work:** the stale ROADMAP bullet is removed and replaced with a reference to this spec.

## Goals

1. Add kit-pass entitlement to the existing subscription row, scoped per draft season.
2. Extend the Stripe checkout flow to sell kit pass alongside draft passes; credit purchase via webhook.
3. Provide a single authoritative entitlements read endpoint for web and extension clients.
4. Gate customization-save (user_kits, league_profiles mutations) and export endpoints on kit-pass possession.
5. Snapshot ranked-list inputs and outputs into `draft_sessions` at clean session close, enabling a post-season ML comparison job between PuckLogic rankings and actual NHL performance.

## Non-Goals (Future Work)

The following are deliberately deferred and require their own specs:

- Refunds (Stripe `charge.refunded` handling and entitlement reversal — both kit pass and draft passes).
- Downgrades (kit-pass → free, refund-prorated or not).
- Gift codes / promo codes.
- Bundles (kit pass + draft passes combined SKU).
- Multi-pass / multi-product entitlements (the scenario that would justify reconsidering a `draft_tokens` or `entitlements` table).
- Structured error envelope for entitlement failures (see API Routes — Error Shape).

## Architecture

Single-tier as today: FastAPI routers → service layer → Supabase repositories. Work clusters into:

- **Schema & repo:** new columns on `subscriptions` and `draft_sessions`; new methods on `subscription_repo`.
- **Stripe integration:** new SKU (`STRIPE_PRICE_KIT_PASS`); `product`-aware checkout creation; webhook dispatcher routing on `metadata.product`; new `credit_kit_pass_for_stripe_event` helper mirroring 008d's draft-pass helper.
- **Read surface:** new `GET /entitlements` endpoint backed by `entitlements_service`.
- **Gating:** new `require_kit_pass` FastAPI dependency reused across customization-save and export endpoints.
- **Session-close hook:** new `snapshot_rankings_at_close` service called from `end_session`, async/best-effort.

## Schema Changes

Single additive migration:

```sql
ALTER TABLE subscriptions
  ADD COLUMN kit_pass_season TEXT,
  ADD COLUMN kit_pass_purchased_at TIMESTAMPTZ;

ALTER TABLE draft_sessions
  ADD COLUMN closing_rankings_snapshot JSONB;
```

Notes:

- Both `kit_pass_*` columns nullable; absence ≡ "no kit pass for any season."
- No CHECK constraint on `kit_pass_season` format; validated at API boundary against `settings.current_season`. Avoids a schema migration on each season rollover.
- No new index. Reads are by `user_id` (already unique-indexed via `subscriptions_user_id_unique` from 008d); kit-pass active/stale check is in-row equality.
- `closing_rankings_snapshot` is nullable; populated only on clean session close. Sessions that expire or abandon without a close get NULL — explicitly acceptable for the ML comparison job, which filters to closed sessions.

### Snapshot JSONB shape

```json
{
  "snapshot_version": 1,
  "captured_at": "2026-09-15T03:14:00Z",
  "season": "2026-27",
  "league_profile_id": "uuid-or-null",
  "scoring_config_id": "uuid",
  "source_weights": {"source_id": 0.4},
  "platform": "espn",
  "rankings": [
    {"player_id": "uuid", "rank": 1, "fantasy_points": 412.3}
  ]
}
```

`snapshot_version` lets the future ML job evolve the shape without a schema migration.

## Stripe Integration

### Configuration

- New env var: `STRIPE_PRICE_KIT_PASS` — Stripe price ID for the $4.99 one-time-per-season kit pass SKU.
- Existing `STRIPE_PRICE_ID` (draft pass) is unchanged. Implementation may rename it to `STRIPE_PRICE_DRAFT_PASS` for clarity in the same change; this is a minor, optional cleanup, not a requirement.

### Checkout flow — `POST /stripe/create-checkout-session`

- Add a required body parameter: `product: "draft_pass" | "kit_pass"`.
- Router selects the matching Stripe price ID.
- Checkout session metadata includes `{user_id, product, season}`. **Season is captured at purchase time**, not at webhook delivery, so a checkout that completes after season rollover credits the season the user actually paid for.

### Webhook crediting

New helper, mirroring `credit_draft_pass_for_stripe_event` from 008d:

```python
credit_kit_pass_for_stripe_event(
    event_id: str,
    user_id: str,
    season: str,
    purchased_at: datetime,
) -> bool
```

Behavior:

- Atomically claims `event_id` via `stripe_processed_events` (`ON CONFLICT DO NOTHING`), preventing duplicate credit on Stripe retries.
- On successful claim, upserts the user's `subscriptions` row, setting `kit_pass_season = :season` and `kit_pass_purchased_at = :purchased_at`.
- **Idempotent and overwrite-safe:** if the user already has `kit_pass_season = :season`, the upsert is a no-op for that field. Crediting a *later* season overwrites the prior season — purchasing in a new season replaces the prior pass; this is the intended product behavior.
- Returns `True` if credited, `False` if event was already processed.

The Stripe webhook dispatcher reads `event.data.object.metadata.product` to route `checkout.session.completed` to either `credit_draft_pass_for_stripe_event` or `credit_kit_pass_for_stripe_event`. Webhook payloads with missing or unknown `product` log a warning and return `200` so Stripe does not retry indefinitely on malformed events.

## API Routes

### `GET /entitlements` (new, auth required)

Returns the authoritative entitlement snapshot for the authenticated user:

```json
{
  "draft_pass_balance": 2,
  "kit_pass": {
    "active": true,
    "season": "2026-27",
    "purchased_at": "2026-08-14T19:22:00Z"
  }
}
```

- `kit_pass.active` is computed: `kit_pass_season == settings.current_season`.
- If `kit_pass_season` is null or stale: `{"active": false, "season": null, "purchased_at": null}`.
- Response includes `Cache-Control: no-store` headers — extension polls this endpoint, and stale reads after a webhook lands are user-visible.

### `POST /stripe/create-checkout-session` (modified)

New required field `product: "draft_pass" | "kit_pass"` (see Stripe Integration). Missing or invalid value returns `422`.

### Gating dependency — `require_kit_pass`

A FastAPI dependency that:

1. Loads the authenticated user's `subscriptions` row (via existing repo).
2. Raises `PermissionError("kit pass required")` if `kit_pass_season != settings.current_season`.

Router-level mapping converts `PermissionError` → HTTP `403` with `detail="kit pass required"`. This **matches the existing draft-pass gating pattern** (`apps/api/routers/draft_sessions.py` raises 403 with a plain-string detail). Consistency with the existing pattern is preferred over introducing a one-off structured error envelope.

### Endpoints gaining `require_kit_pass`

- `POST /user-kits` — save customized kit (was auth-only).
- `PATCH /user-kits/{id}` and `DELETE /user-kits/{id}`.
- `POST /league-profiles` and league-profile mutations — kit pass gates *saving* configuration, per spec 009 entitlement matrix.
- Export endpoints (Excel and PDF generation routes). The implementation plan must verify the current export route names against `apps/api/routers/` before wiring; spec 009 states export is included with kit pass and not sold separately, so all export-trigger endpoints are gated.

### Endpoints **not** gated

- `POST /rankings/compute` — free tier may compute rankings against a temporary in-browser kit (per spec 009).
- `GET /user-kits` — read-only listing of one's own saved kits. Free-tier users will have none, so the gate adds nothing.
- `GET /entitlements` — by definition open to all authenticated users.

### Error Shape — design tradeoff (deferred)

The plain-string `403` payload is consistent with draft-pass gating but provides no machine-readable error code or purchase URL for the FE/extension to drive a "Buy kit pass" CTA. The spec defers this question. A follow-up may introduce a structured `ErrorEnvelope` for entitlement failures **across both** draft-pass and kit-pass paths, once frontend integration reveals concrete pain. Out of scope here.

## Service / Repo Layer

### `subscription_repo` additions

```python
def get_kit_pass(user_id: str) -> dict | None:
    """Returns {'season': str | None, 'purchased_at': datetime | None}, or None
    if no subscriptions row exists for the user."""

def credit_kit_pass_for_stripe_event(
    event_id: str,
    user_id: str,
    season: str,
    purchased_at: datetime,
) -> bool:
    """Atomic. Claims event_id via stripe_processed_events, then upserts
    subscriptions.kit_pass_season + kit_pass_purchased_at. Returns True on
    credit, False on already-processed event. Mirrors the 008d draft-pass
    helper exactly."""

def has_active_kit_pass(user_id: str, current_season: str) -> bool:
    """Single-query equality check against the user's subscriptions row."""
```

### `entitlements_service` (new)

```python
def get_entitlements(user_id: str) -> EntitlementsResponse:
    """Single DB read of the user's subscriptions row; returns combined
    draft_pass_balance + kit_pass shape. Treats missing row as zero balance
    and inactive kit pass."""
```

### Session close snapshot (new)

```python
def snapshot_rankings_at_close(session_id: str, user_id: str) -> None:
    """Called from end_session() after the session row transitions to terminal
    status. Pulls the inputs that produced rankings for this session
    (league_profile_id, scoring_config_id, source_weights, platform from the
    session record) and recomputes the ranked list against current
    player_projections / player_stats. Writes the JSONB snapshot.

    Best-effort and async: invoked after end_session returns 204 to the client.
    Failure logs and does not block session close; an ML-job retry sweep
    handles gaps for sessions where snapshot is NULL after a grace period."""
```

**Recompute vs. cached lookup — decided.** Snapshot **recomputes** rankings from the session's stored inputs against current `player_projections` / `player_stats`. Rationale:

- Within a typical 1–3 hour draft session window, weekly-cadence projection scrapers (Mondays 06:00 UTC) almost never land mid-session; recomputed rankings will match what the user saw in nearly all cases.
- The post-season ML comparison job needs deterministic, reproducible inputs to compare against actual NHL performance. Recompute against stored inputs is reproducible from cold storage; cached reads are not (cache TTL is 6h; long sessions miss).
- Async writeback removes the latency cost from `end_session` itself.

If post-launch monitoring shows meaningful drift, a `rankings_source: "cache" | "recompute"` flag may be added in a follow-up — out of scope here.

### Stripe router

Webhook dispatcher routes `checkout.session.completed` events on `event.data.object.metadata.product` to either `credit_draft_pass_for_stripe_event` (existing) or `credit_kit_pass_for_stripe_event` (new). Same `stripe_processed_events` table guards both helpers; same idempotency contract.

## Testing Strategy

TDD discipline per repo convention; tests written before implementation. Files: `apps/api/tests/services/test_subscriptions.py`, `test_entitlements.py`, `test_draft_sessions.py`; `apps/api/tests/routers/test_stripe.py`, `test_entitlements.py`, gated routers' existing test files.

### Unit — repos and services

- `subscription_repo.credit_kit_pass_for_stripe_event`:
  - First call credits and returns True.
  - Second call with the same `event_id` is no-op and returns False.
  - Crediting a later season for the same user overwrites the season field.
  - Concurrent-call safety via the `stripe_processed_events` claim (one wins, others no-op).
- `subscription_repo.has_active_kit_pass`:
  - True when `kit_pass_season == current_season`.
  - False on null season; false on stale season.
- `entitlements_service.get_entitlements`:
  - Composes draft balance + active kit pass from a single subscriptions read.
  - User with no `subscriptions` row returns `{draft_pass_balance: 0, kit_pass: {active: false, season: null, purchased_at: null}}`.
- `snapshot_rankings_at_close`:
  - Writes the documented JSONB shape, including `snapshot_version: 1`.
  - Missing-input session is a logged no-op; does not raise.
  - Failure during recompute logs and does not propagate; session close still succeeds.

### Router

- `GET /entitlements`:
  - 401 without auth.
  - Returns correct shape for active, stale, and no-pass users.
  - Response carries `Cache-Control: no-store`.
- `POST /stripe/create-checkout-session`:
  - `product=kit_pass` selects `STRIPE_PRICE_KIT_PASS`.
  - `product=draft_pass` selects the existing draft-pass price.
  - Missing or unrecognized `product` returns 422.
- Stripe webhook:
  - `kit_pass` product completes → `subscriptions.kit_pass_season` populated; `purchased_at` recorded.
  - Replay of the same event → no second update, returns 200.
  - Webhook with no metadata or unknown product → logged and returns 200.
- `require_kit_pass` dependency, per gated route (user-kits create/update/delete, league-profiles mutations, exports):
  - Free-tier user → 403 `"kit pass required"`.
  - Active kit-pass user → passes through.

### Integration

- End-to-end Stripe flow with the test webhook fixtures: checkout → webhook → entitlement reads true → gated endpoint allows → simulated season rollover (config bump) → entitlement reads false → gated endpoint blocks.
- Session close: snapshot present in `draft_sessions.closing_rankings_snapshot` after a clean close; abandoned/expired session has NULL snapshot.

### Out of scope for this spec's tests

- Refund webhook handling, downgrade flows, gift codes (deferred per Non-Goals).
- Live Stripe API tests (covered in existing CI Stripe harness).

## Documentation Touch Points

- Remove the stale `draft_tokens` bullet from `docs/ROADMAP.md` (Milestone C backend additions); replace with reference to this spec.
- Update `docs/backend-reference.md`:
  - Add the two new `subscriptions` columns to the schema block.
  - Add `closing_rankings_snapshot` to the `draft_sessions` schema block.
  - Document `GET /entitlements`, the modified Stripe checkout signature, and `STRIPE_PRICE_KIT_PASS`.
  - Note in the existing 008d-resolution comment block that kit-pass also lives on `subscriptions`, reaffirming the no-new-table launch decision.
- Update `docs/extension-reference.md` to point the extension at `GET /entitlements` for balance and kit-pass status.
- Update `docs/specs/INDEX.md` with this spec.

## Open Questions

None blocking. The Error Shape tradeoff is captured as deferred; the recompute decision is final pending post-launch evidence to the contrary.

## Implementation Sequencing Hint

The implementation plan derived from this spec should sequence roughly:

1. Migration + repo methods + repo tests.
2. `entitlements_service` + `GET /entitlements` + tests.
3. Stripe checkout `product` parameter + webhook dispatch + `credit_kit_pass_for_stripe_event` + tests.
4. `require_kit_pass` dependency + gating on user-kits / league-profiles / exports + tests.
5. Session-close snapshot writeback + tests.
6. Documentation updates (ROADMAP, backend-reference, extension-reference, specs index).

The plan author should verify exact route names for export endpoints against `apps/api/routers/` at plan-writing time.
