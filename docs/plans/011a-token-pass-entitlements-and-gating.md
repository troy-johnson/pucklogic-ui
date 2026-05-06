# Plan: Token Pass Entitlements and Gating

**Spec basis:** `docs/specs/011-milestone-c-token-pass-backend.md`  
**Branch:** `feat/011a-token-pass-entitlements`  
**Risk Tier:** 3 — billing + auth gating + schema  
**Scope:** Medium (~1–2 days)  
**Execution mode:** Dependency waves  
**Execution status:** Approved on 2026-04-30  
**Readiness:** Ready for implement-tdd  
**Key decisions:** `kit_pass.purchase_url` is `null` when `active=true`; otherwise it is constructed from `settings.frontend_url` plus the existing checkout-session route. Gated routes reuse the existing draft-pass plain-string 403 response pattern.

---

## Goal
Implement the launch entitlement path for kit pass purchase, Stripe crediting, `GET /entitlements`, and gated write/export routes.

## Non-Goals
- Refunds or entitlement reversal
- Downgrades
- Promo/gift code support
- Generic entitlement tables
- New structured entitlement error envelope

---

## File Surface

### Created
| File | Change |
|---|---|
| `supabase/migrations/009_token_pass_entitlements.sql` | Add kit-pass fields to `subscriptions` needed by Stripe crediting and entitlement reads |
| `apps/api/services/entitlements.py` | Central entitlement read/gating logic |
| `apps/api/routers/entitlements.py` | Authenticated `GET /entitlements` route |
| `apps/api/tests/services/test_entitlements.py` | Unit coverage for entitlement shape and stale/active/no-pass states |
| `apps/api/tests/routers/test_entitlements.py` | Router coverage for authenticated `GET /entitlements` and response headers |

### Modified
| File | Change |
|---|---|
| `apps/api/repositories/subscriptions.py` | Add kit-pass season/state read helpers and Stripe idempotent credit rules |
| `apps/api/routers/stripe.py` | Add kit-pass checkout product routing and webhook handling |
| `apps/api/core/dependencies.py` | Add reusable `require_kit_pass` dependency |
| `apps/api/routers/user_kits.py` | Gate create/delete routes; keep list route open |
| `apps/api/routers/league_profiles.py` | Gate create route |
| `apps/api/routers/exports.py` | Gate export generation route |
| `apps/api/models/schemas.py` | Add entitlements response schema and any Stripe metadata schema adjustments |
| `apps/api/main.py` | Register entitlements router |
| `apps/api/tests/repositories/test_subscriptions.py` | Cover same-season, later-season, earlier-season, and no-op Stripe credit cases |
| `apps/api/tests/routers/test_stripe.py` | Cover checkout metadata and unknown/missing webhook product handling |
| `apps/api/tests/routers/test_user_kits.py` | Cover gated create/delete and ungated list |
| `apps/api/tests/routers/test_league_profiles.py` | Cover gated create |
| `apps/api/tests/routers/test_exports.py` | Cover gated export and free-tier compute regression |
| `apps/api/tests/test_dependencies.py` | Cover `require_kit_pass` dependency behavior |
| `docs/backend-reference.md` | Document `GET /entitlements`, kit-pass gating, and unlimited export behavior |
| `docs/extension-reference.md` | Document entitlement read path and `purchase_url` behavior |
| `docs/ROADMAP.md` | Replace stale `draft_tokens` roadmap wording with a spec 011 reference |

### Deleted
- None

---

## Implementation Phases
### Phase 1 — Lock failing coverage
Add tests first for Stripe credit rules, entitlement reads, and gated routes.

### Phase 2 — Add persistence and domain logic
Add subscription schema fields, repository helpers, and entitlement service.

### Phase 3 — Wire API surfaces
Expose checkout metadata, webhook handling, entitlement route, and route dependency gating.

### Phase 4 — Update canonical docs and verify
Refresh backend/extension/roadmap docs and run focused verification.

## Task List

### Wave 1 — RED coverage
1. **Add failing repository tests for kit-pass Stripe credit idempotency.**  
   Command: `Edit apps/api/tests/repositories/test_subscriptions.py`  
   Expected: Tests assert same-season no-op, later-season overwrite, earlier-season warn-and-skip, and active/stale read behavior.

2. **Add failing Stripe router tests for checkout metadata and webhook fallback behavior.**  
   Command: `Edit apps/api/tests/routers/test_stripe.py`  
   Expected: Tests assert checkout metadata includes `user_id`, `product`, `season`; unknown/missing product returns 200 and logs warning.

3. **Add failing entitlement service and router tests for active, stale, and no-pass responses.**  
   Command: `Create apps/api/tests/services/test_entitlements.py and apps/api/tests/routers/test_entitlements.py`  
   Expected: Tests assert auth required, correct response shape, and `Cache-Control: no-store`.

4. **Add failing user-kits gating tests.**  
   Command: `Edit apps/api/tests/routers/test_user_kits.py`  
   Expected: Tests assert `POST /user-kits` and `DELETE /user-kits/{id}` require a kit pass while `GET /user-kits` remains allowed.

5. **Add failing league-profiles and exports gating tests, including compute regression.**  
   Command: `Edit apps/api/tests/routers/test_league_profiles.py and apps/api/tests/routers/test_exports.py`  
   Expected: Tests assert `POST /league-profiles` and `POST /exports/generate` require a kit pass while free-tier `POST /rankings/compute` remains allowed.

### Wave 2 — Persistence + domain
6. **Create the entitlement migration.**  
   Command: `Create supabase/migrations/009_token_pass_entitlements.sql`  
   Expected: Migration adds only the approved kit-pass fields on `subscriptions` with additive, reversible-safe schema changes.

7. **Implement kit-pass repository helpers and Stripe credit rules.**  
   Command: `Edit apps/api/repositories/subscriptions.py`  
   Expected: Repository exposes entitlement reads plus idempotent Stripe credit behavior matching the spec.

8. **Implement entitlement response models and domain service.**  
   Command: `Edit apps/api/models/schemas.py and create apps/api/services/entitlements.py`  
   Expected: Service returns the approved `GET /entitlements` shape for active, stale, and no-pass users.

### Wave 3 — API wiring
9. **Update Stripe checkout and webhook routing for kit pass.**  
   Command: `Edit apps/api/routers/stripe.py`  
   Expected: Checkout sessions set `user_id`/`product`/`season`; webhook dispatches to kit-pass credit logic and preserves 200 on unknown product.

10. **Expose the authenticated entitlements route.**  
    Command: `Create apps/api/routers/entitlements.py and edit apps/api/main.py`  
    Expected: `GET /entitlements` is registered, auth-protected, and returns `Cache-Control: no-store`.

11. **Add reusable kit-pass dependency and apply it to user-kits writes.**  
    Command: `Edit apps/api/core/dependencies.py and apps/api/routers/user_kits.py`  
    Expected: Shared dependency enforces kit-pass access on create/delete without affecting list behavior.

12. **Apply kit-pass gating to league-profile creation and export generation.**  
    Command: `Edit apps/api/routers/league_profiles.py and apps/api/routers/exports.py`  
    Expected: Gated routes deny non-entitled users and continue allowing non-gated compute flows.

### Wave 4 — Docs + verification
13. **Update canonical docs and roadmap references for entitlements and gated behaviors.**  
    Command: `Edit docs/backend-reference.md docs/extension-reference.md and docs/ROADMAP.md`  
    Expected: Docs describe `GET /entitlements`, kit-pass gating, unlimited export entitlement, `purchase_url` behavior, and replace stale `draft_tokens` roadmap wording with a reference to spec 011.

14. **Run focused verification for entitlement, billing, and gating paths.**  
    Command: `python -m pytest apps/api/tests/repositories/test_subscriptions.py apps/api/tests/services/test_entitlements.py apps/api/tests/routers/test_entitlements.py apps/api/tests/routers/test_stripe.py apps/api/tests/routers/test_user_kits.py apps/api/tests/routers/test_league_profiles.py apps/api/tests/routers/test_exports.py apps/api/tests/test_dependencies.py`  
    Expected: All targeted tests pass with no entitlement-regression failures.

---

## Verification Mapping
| Acceptance need | Tasks / Covered by |
|---|---|
| Kit pass purchasable via Stripe product | 2, 9, 14 |
| Checkout metadata includes `user_id`, `product`, `season` | 2, 9, 14 |
| Webhook credits correct product and is idempotent | 1, 7, 9, 14 |
| Same-season no-op / later overwrite / earlier no-regression | 1, 7, 14 |
| Unknown/missing webhook product warns and returns 200 | 2, 9, 14 |
| `GET /entitlements` exists, auth-required, correct shape | 3, 8, 10, 14 |
| `Cache-Control: no-store` on entitlements response | 3, 10, 14 |
| `POST /user-kits` gated | 4, 11, 14 |
| `DELETE /user-kits/{id}` gated | 4, 11, 14 |
| `POST /league-profiles` gated | 5, 12, 14 |
| `POST /exports/generate` gated | 5, 12, 14 |
| `POST /rankings/compute` remains free-tier | 5, 12, 14 |
| `GET /user-kits` remains ungated | 4, 11, 14 |
| `GET /entitlements` remains available to authenticated users | 3, 10, 14 |

## Risks
- Stripe webhook ordering/replay bugs can silently corrupt entitlement state if repository logic is not the single authority.
- Route-level gating must not change existing non-gated read/compute behaviors.
- Axon state still referenced `draft_tokens` before this plan; implementation should keep docs/state wording aligned with the approved spec.

## Open Questions
- None.
