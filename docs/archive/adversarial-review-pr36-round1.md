# Adversarial Review Packet — PR #36

- **PR:** #36 — `feat(api): implement milestone C entitlements and close-time snapshots`
- **URL:** https://github.com/troy-johnson/pucklogic-ui/pull/36
- **Reviewer:** review
- **Date:** 2026-05-02
- **Round:** 1
- **Verdict:** REVISE
- **Ship gate:** BLOCKED

## Review basis

This packet evaluates PR #36 against:

- `docs/specs/011-milestone-c-token-pass-backend.md`
- `docs/plans/011a-token-pass-entitlements-and-gating.md`
- `docs/plans/011b-session-close-rankings-snapshot.md`

Risk tags in scope:

- payments
- auth / entitlement gating
- schema / migration
- production-state mutation

## Executive summary

The PR closes several previously identified Spec 011 gaps, including:

- single-read entitlement shaping
- inactive kit-pass purchase URL contract
- `closing_rankings_snapshot` naming/schema alignment
- close-time snapshot payload semantics

However, the ship gate remains **blocked** by two spec-level blockers in the payments path:

1. the repo contains Python callsites for `credit_kit_pass_for_stripe_event` but no SQL/RPC definition for that helper
2. the implementation does not capture/pass `purchased_at`, so the spec’s timestamp semantics for same-season preserve / later-season overwrite are not implementable

## Stage 1 — Spec compliance

### AC-1 — Entitlements live on `subscriptions`; no new entitlement table

- **Status:** ACCEPT
- **Evidence:** `supabase/migrations/009_token_pass_entitlements.sql`

### AC-2 — `GET /entitlements` authoritative read surface with no-store and CTA URL

- **Status:** ACCEPT
- **Evidence:**
  - mounted in `apps/api/main.py`
  - route in `apps/api/routers/entitlements.py`
  - single-row read in `apps/api/repositories/subscriptions.py:get_entitlements_state`
  - response shaping in `apps/api/services/entitlements.py`

### AC-3 — Checkout session supports `product` and Stripe metadata `{user_id, product, season}`

- **Status:** ACCEPT
- **Evidence:** `apps/api/routers/stripe.py`, `apps/api/tests/routers/test_stripe.py`

### AC-4 — Kit-pass webhook credit helper exists and satisfies idempotent season/timestamp semantics

- **Status:** REJECT
- **Why:**
  - no SQL definition for `credit_kit_pass_for_stripe_event` found in repo migrations
  - helper signature omits `purchased_at`
  - router does not pass purchase timestamp
- **Impact:** paid kit-pass purchases can fail or drift from spec/audit contract

### AC-5 — Kit-pass gating applied to save/export routes only

- **Status:** ACCEPT
- **Evidence:** `require_kit_pass` and gated router tests

### AC-6 — Persist recipe inputs and write `closing_rankings_snapshot` on clean close

- **Status:** ACCEPT
- **Evidence:** migration `010_session_close_rankings_snapshot.sql`, draft session repo/service/router wiring

### AC-7 — Snapshot recomputes from persisted recipe and stores `{player_id, rank, fantasy_points}`

- **Status:** ACCEPT
- **Evidence:** `apps/api/services/draft_sessions.py:_build_close_snapshot`

### AC-8 — Integration coverage for full entitlement and snapshot flows

- **Status:** PARTIAL
- **Why:** component tests exist, but no direct end-to-end test was found for:
  - checkout → webhook → entitlement active → gated allow → rollover → entitlement inactive → gated block
  - clean close followed by snapshot presence
  - expired/abandoned session explicitly asserting null/no snapshot

## Stage 2 — Adversarial findings

## Blockers

### B1 — Missing DB/RPC implementation for `credit_kit_pass_for_stripe_event`

- **Risk:** blocker
- **Area:** payments / production
- **Evidence:**
  - callsite: `apps/api/repositories/subscriptions.py`
  - router usage: `apps/api/routers/stripe.py`
  - no matching SQL function found in repo migrations
- **Why it matters:** successful Stripe webhooks can reach a nonexistent backend DB function and fail at runtime.
- **Required fix:** add the SQL/RPC implementation and tests/evidence that the function exists with the expected contract.

### B2 — `purchased_at` contract is not implemented

- **Risk:** blocker
- **Area:** payments / auditability
- **Evidence:**
  - spec requires `credit_kit_pass_for_stripe_event(event_id, user_id, season, purchased_at)`
  - implementation uses `(event_id, user_id, season)` only
  - webhook does not pass purchase timestamp
- **Why it matters:** same-season preserve semantics and later-season overwrite semantics for `kit_pass_purchased_at` cannot be honored.
- **Required fix:** capture Stripe purchase timestamp, pass it through router/repo/RPC, and implement the documented same-season/later-season behavior.

## Important findings

### I1 — Missing-header webhook path under-defended

- **Risk:** important
- **Area:** auth / payments
- **Evidence:** `stripe_signature` optional; only signature-verification exception explicitly handled.
- **Why it matters:** malformed webhook requests may 500 instead of returning a controlled client error.
- **Suggested fix:** harden missing-header / malformed-body handling and add direct tests.

### I2 — Integration coverage is fragmented instead of flow-complete

- **Risk:** important
- **Area:** regression safety
- **Why it matters:** the highest-risk user journey crosses Stripe, entitlement state, and gated routes; fragmented tests are weaker against contract drift.
- **Suggested fix:** add at least one direct entitlement lifecycle test and one direct close-vs-expired snapshot behavior test.

### I3 — Negative `source_weights` appear persistable

- **Risk:** important
- **Area:** correctness
- **Evidence:** validators reject all-zero, but not negative values.
- **Why it matters:** invalid recipes can be persisted and later replayed into snapshot recomputation.
- **Suggested fix:** reject negative weights at request-schema boundary.

## Minor findings

### M1 — Legacy snapshot helper remains alongside new canonical snapshot builder

- **Risk:** minor
- **Area:** maintainability
- **Why it matters:** future contributors may use the wrong snapshot path.

### M2 — Draft-session tests are oversized and repetitive

- **Risk:** minor
- **Area:** maintainability
- **Why it matters:** increases review/debug cost and can hide edge-case omissions.

## Required actions before ship-sync

1. Implement and migrate the DB/RPC function for `credit_kit_pass_for_stripe_event`
2. Add `purchased_at` plumbing from Stripe event through repo/RPC semantics
3. Add focused tests proving the timestamp/idempotency behavior
4. Harden webhook error handling for missing signature / malformed payload
5. Add direct integration tests for:
   - entitlement lifecycle across season rollover
   - clean-close snapshot present
   - expired/abandoned snapshot absent/null

## Final adversarial disposition

- **Verdict:** REVISE
- **Round:** 1
- **Ship gate:** BLOCKED

The PR should not move to ship-sync until the two payment-contract blockers are resolved.
