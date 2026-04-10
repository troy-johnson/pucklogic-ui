# PuckLogic Implementation Review

**Reviewer:** Codex  
**Date:** March 12, 2026

## Review Basis

This review treats the following as the intended implementation plan:

- `AGENT.md`
- `docs/pucklogic_architecture_v2.md`
- `docs/phase-1-backend.md`
- `docs/phase-1-frontend.md`
- `docs/phase-2-backend.md`
- `docs/phase-2-frontend.md`
- `docs/phase-3-backend.md`
- `docs/phase-3-frontend.md`
- `docs/phase-4-backend.md`
- `docs/phase-4-frontend.md`
- `docs/v2-backend.md`
- `docs/v2-frontend.md`

When those documents conflict with `docs/claude-code-reference.md` or older schema examples, this review treats the phase docs plus architecture docs as canonical.

## Overall Assessment

The product direction is strong and the phased rollout is sensible. The main risks are not weak ideas or missing ambition. The risk is that several critical flows are still not decision-complete, and multiple docs define incompatible schemas, route contracts, and security boundaries. If those conflicts are not resolved before implementation continues, the project will accumulate avoidable migration churn, integration failures, and monetization leaks.

## Findings

### 1. Critical — `implementation`, `design`, `security`
### Stripe and subscription flow is not decision-complete

**Evidence**

- `docs/phase-2-frontend.md` Section 6.2 creates a Stripe Checkout session in a Next.js route at `/api/stripe/create-checkout-session`.
- `docs/phase-2-backend.md` Section 5.1 defines a FastAPI webhook at `/webhooks/stripe` and upserts subscriptions by `stripe_customer_id`.
- `docs/phase-2-frontend.md` Section 6.4 polls `/api/subscriptions/me`, but that route is not defined in the backend docs or canonical route maps.
- `docs/claude-code-reference.md` route map uses different names again: `/api/stripe/checkout` and `/api/stripe/webhook`.
- `docs/phase-2-backend.md` webhook handlers never define how Stripe events map back to `auth.users.id`. The example upsert takes `stripe_customer_id`, `stripe_subscription_id`, `plan`, `status`, and `expires_at`, but not the owning application user.

**Why this matters**

As written, the subscription gate cannot be implemented reliably. The frontend expects subscription state to become visible immediately after checkout, but the backend flow does not specify how a Stripe customer or subscription is associated with the authenticated PuckLogic user. That leaves the paid gate, billing page, and export entitlement path under-defined.

**Canonical direction**

Define one payment architecture and make every doc follow it:

- Use one authenticated server-side route to create checkout sessions.
- Attach `user_id` through Stripe `client_reference_id` or metadata.
- Persist the Stripe-to-user mapping explicitly.
- Define a canonical `GET /api/subscriptions/me` response.
- Standardize route names across web and API docs.

**Suggested implementation standard**

- Subscription checkout creation should be authenticated and server-side.
- Webhook processing should upsert by `user_id` plus Stripe identifiers, not by Stripe customer ID alone.
- The billing page should read a documented `/api/subscriptions/me` route or an explicitly documented Next.js proxy that wraps the backend.

---

### 2. Critical — `implementation`, `design`
### Phase 4 extension contracts are internally incompatible

**Evidence**

- `docs/phase-4-frontend.md` service worker sends `pick` messages with `player_name` and `pickNumber`.
- `docs/phase-4-backend.md` Section 2.1 defines `pick` payload as `{player_id, player_name, round, pick}`.
- `docs/phase-4-frontend.md` manual pick flow sends only `player_name`, `round`, and `pick`.
- `docs/phase-4-backend.md` handler calls `process_pick(... player_id=data["player_id"], round=data["round"], pick=data["pick"])`, so the documented frontend payload would fail.
- `docs/phase-4-frontend.md` `handleConfigSubmit` and `handlePaymentSuccess` call `/api/stripe/create-draft-payment-intent` and `/api/draft/create-session` without showing JWT forwarding.
- `docs/phase-4-backend.md` `create_draft_session` requires `current_user: User = Depends(get_current_user)` and verifies `intent.metadata["user_id"] == current_user.id`.

**Why this matters**

The extension and backend cannot interoperate as documented. Pick ingestion is the core value of Phase 4, and the current contracts would either reject valid frontend messages or force last-minute undocumented glue logic. The draft payment/session flow has the same problem on the auth boundary.

**Canonical direction**

Publish one canonical Phase 4 message protocol and one authenticated request pattern:

- Either require `player_id` on all `pick` messages or explicitly add a backend name-resolution step.
- Standardize field names: choose `pick` or `pick_number`, not both.
- Document how the web app forwards Supabase auth to protected draft routes.
- Define reconnect/state recovery behavior in the same contract document.

**Suggested implementation standard**

- Content script emits a normalized `DetectedPick` payload.
- Service worker translates to a backend `pick` contract only after player resolution.
- Backend supports `sync_state` on reconnect if MV3 worker termination is expected.

---

### 3. Critical — `security`, `design`
### Extension auth and session handoff expose avoidable security risks

**Evidence**

- `docs/phase-4-backend.md` authenticates the draft WebSocket with `?token=<jwt>`.
- `docs/phase-4-frontend.md` creates the WebSocket with `new WebSocket(`${wsUrl}?token=${pucklogic_token}`)`.
- `docs/phase-4-frontend.md` uses `window.postMessage({ type: "PUCKLOGIC_SESSION", session_id, ws_url }, window.origin)` to hand session data to a content script.
- The docs do not define the receiving bridge, origin validation, schema validation, replay protection, TTL, or one-time semantics for that message.
- `docs/phase-4-frontend.md` stores extension credentials in `chrome.storage.local`, and the same document stores `pucklogic_token` there for WebSocket auth.

**Why this matters**

JWTs in query strings are easier to leak through logs, debugging, and intermediaries. The `postMessage` bridge is an untrusted boundary, and the current plan does not define how spoofed or replayed messages are rejected. Storing broad, long-lived credentials in `chrome.storage.local` expands the blast radius of extension compromise.

**Canonical direction**

Replace the current model with a short-lived, least-privilege session mechanism:

- Do not pass Supabase JWTs in WebSocket query params.
- Issue a short-lived draft WebSocket ticket from an authenticated REST endpoint.
- Define an explicit receiver for `postMessage` with strict origin checks and payload schema validation.
- Store the minimum viable session artifact, with expiry and rotation rules.

**Suggested safer alternative**

- Web app calls authenticated REST endpoint to mint a single-use draft ticket.
- Extension receives only `session_id`, `ws_url`, and `draft_ticket`.
- Backend exchanges `draft_ticket` for the WebSocket session and invalidates it after first use.
- Any page-to-extension bridge validates origin, message type, nonce, and expiry.

---

### 4. High — `implementation`, `design`
### Anonymous kit support is required by intent but not implementable from the current docs

**Evidence**

- `docs/pucklogic_architecture_v2.md` Section 5.4 requires anonymous users to build kits by session token, auto-migrate them on sign-up/login, and clean them up after 7 days.
- `docs/pucklogic_architecture_v2.md` RLS summary says `user_kits` are accessible where `auth.uid() = user_id OR session_token matches`.
- `docs/claude-code-reference.md` also models `user_kits` with `session_token` and a cookie-based RLS example.
- `docs/phase-1-backend.md` RLS for `user_kits` only allows `auth.uid() = user_id`.
- `docs/phase-1-frontend.md` implements a fully protected `/dashboard/*` shell and does not define anonymous kit creation, storage, or migration.
- No doc defines the 7-day cleanup mechanism beyond mentioning that it should exist.

**Why this matters**

Anonymous kit support is not a cosmetic feature. It changes the user journey, route access, persistence model, and auth migration flow. As written, the launch architecture says anonymous kits are part of v1 but the phase docs do not provide a working path to implement them.

**Canonical direction**

Choose one of two paths and update all docs accordingly:

- Fully specify anonymous kits end to end.
- Remove anonymous kits from v1 and require auth before kit persistence.

Given the stated launch intent, the first path is the consistent one.

**Suggested implementation standard**

- Define anonymous-accessible kit routes.
- Define cookie issuance and server-side session-token handling.
- Define migration on login/signup.
- Define cleanup job ownership and schedule.

---

### 5. High — `security`, `design`
### The security model mixes DB-enforced RLS with app-enforced auth in incompatible ways

**Evidence**

- `docs/phase-1-backend.md` presents Supabase Auth plus RLS as a foundation decision.
- `docs/pucklogic_architecture_v2.md` and `docs/claude-code-reference.md` describe owner-scoped access at the database layer.
- `docs/phase-1-backend.md` environment variables include `SUPABASE_SERVICE_KEY`.
- Backend examples in `docs/phase-2-backend.md`, `docs/phase-3-backend.md`, and `docs/phase-4-backend.md` use server-side Supabase clients and custom JWT middleware or `get_current_user` dependencies.
- `docs/claude-code-reference.md` proposes RLS logic using `current_setting('request.cookies')`, but service-role database access bypasses that model unless the request context is re-projected explicitly.

**Why this matters**

Right now the docs imply two different enforcement models:

- Database RLS is the primary guardrail.
- FastAPI application code is the primary guardrail.

Those are not interchangeable. If most backend operations run with the service role, then the API layer is the real security boundary and must consistently enforce ownership and entitlement checks. The current docs do not state that clearly.

**Canonical direction**

Document the security model explicitly:

- Public/shared data can use service-role reads/writes under app control.
- User-owned data must name the enforcement point per route.
- If service-role access is used for user-owned tables, every route must document and test ownership checks.

**Suggested implementation standard**

Add a security section that classifies each table and endpoint as one of:

- RLS-enforced direct access
- API-enforced service-role access
- Hybrid, with explicit reasoning

---

### 6. High — `documentation drift`, `implementation`
### Schema drift is already large enough to create migration churn and implementation mistakes

**Evidence and conflicts**

| Area | Conflicting docs | Conflict |
|---|---|---|
| `player_rankings` source identity | `docs/phase-1-backend.md` vs `docs/claude-code-reference.md` | `source TEXT` vs `source_id UUID REFERENCES sources(id)` |
| `user_kits` model | `docs/phase-1-backend.md`, `docs/phase-3-backend.md` vs `docs/claude-code-reference.md`, `docs/pucklogic_architecture_v2.md` | `weights` + `league_format` + `scoring_settings` vs `source_weights` + `scoring_config_id` + `session_token` |
| `player_trends` explainability fields | `docs/phase-1-backend.md`, `docs/claude-code-reference.md`, `docs/phase-3-backend.md` | `shap_json` vs `shap_values` vs `shap_top3` |
| Projection storage | `docs/claude-code-reference.md` vs `docs/phase-3-backend.md` | inline `projected_stats JSONB` vs separate `player_projections` table |
| `season` type | `docs/phase-1-backend.md`, `docs/phase-3-backend.md`, `docs/v2-backend.md` | `TEXT` like `2024-25`, `SMALLINT`, and API `int`/`str` usage |
| player birth/age fields | `AGENT.md`, `docs/phase-1-backend.md`, `docs/claude-code-reference.md`, `docs/phase-3-backend.md` | `dob` or `date_of_birth` in schema, but trends queries select `players.age` |
| `player_trends` uniqueness | `docs/claude-code-reference.md` vs phase docs | `UNIQUE(player_id)` vs season-scoped uniqueness |

**Why this matters**

This is no longer normal documentation drift. Multiple teams or future agents could implement valid-looking but incompatible migrations from these docs. The result would be wasted effort, broken joins, and avoidable refactors.

**Canonical direction**

Add one explicit canonical schema section and deprecate the rest. The phase docs should reference that canonical schema instead of redefining core tables independently.

**Recommended canonical choices**

- `season`: use `TEXT` in the canonical NHL season form, such as `2026-27`.
- `player_rankings`: use `source_id UUID` rather than free-form source text.
- `user_kits`: support `session_token`, `source_weights`, `league_format`, and either inline `scoring_settings` or a normalized `scoring_config_id`, but not both without clear precedence.
- `player_trends`: store only trend/explainability fields there; keep detailed projections in `player_projections`.
- `players`: store `date_of_birth`; compute `age` in queries or materialized views rather than storing both unsafely.

---

### 7. High — `documentation drift`, `implementation`
### Public API drift is substantial enough to break frontend/backend alignment

**Evidence and conflicts**

| Resource | Conflicting docs | Conflict |
|---|---|---|
| Rankings | `docs/claude-code-reference.md` vs `docs/phase-2-backend.md` / `docs/phase-2-frontend.md` | `GET /api/rankings` vs `POST /api/rankings/compute` |
| Trends | `docs/claude-code-reference.md` vs `docs/phase-3-backend.md` / `docs/v2-backend.md` | `/api/trends/{player_id}`, `/api/trends/breakouts`, `/api/trends/regressions` vs a list endpoint at `/api/trends` |
| Draft sessions | `docs/claude-code-reference.md` vs `docs/phase-4-backend.md` | `/api/draft/session` vs `/api/draft/create-session` |
| Exports | `docs/claude-code-reference.md` vs `docs/phase-2-backend.md` | async `/api/exports/pdf` + status/download endpoints vs synchronous `GET /api/exports/generate` |
| Stripe | `docs/claude-code-reference.md`, `docs/phase-2-frontend.md`, `docs/phase-2-backend.md` | `/api/stripe/checkout`, `/api/stripe/create-checkout-session`, `/api/stripe/webhook`, `/webhooks/stripe` |

**Why this matters**

API drift causes implementation thrash even when the underlying feature ideas are sound. The current docs would lead different implementers to build different route maps, request bodies, and entitlement checks.

**Canonical direction**

Publish one route map per bounded area:

- Rankings
- Trends
- Billing/subscriptions
- Draft sessions
- Exports

Every frontend doc should consume only those canonical endpoints.

---

### 8. Medium — `feature gap`, `design`
### Product scope is drifting across docs

**Evidence**

- `docs/pucklogic_architecture_v2.md` says launch scope is skaters only.
- `docs/phase-1-backend.md` NHL scraper fetches `forwards + defensemen + goalies`.
- `docs/phase-2-backend.md` `_compute_vorp` includes goalie replacement logic.
- `docs/pucklogic_architecture_v2.md` says Phase 4 includes ESPN + Yahoo adapters.
- `AGENT.md` and Phase 4 documents emphasize ESPN specifically.
- `docs/pucklogic_architecture_v2.md` and `docs/claude-code-reference.md` describe a sidebar-based extension architecture, while `docs/phase-4-frontend.md` is popup-centric.

**Why this matters**

Scope drift increases implementation cost by encouraging developers to scaffold non-launch features early. It also obscures which assumptions are safe for schema and UI design.

**Canonical direction**

Mark launch scope explicitly:

- v1: skaters only
- Phase 4 launch: ESPN only unless Yahoo is explicitly funded into scope
- Extension UI: choose popup or sidebar as the primary Phase 4 surface

Everything else should move to backlog or “post-launch” sections.

---

### 9. Medium — `design`, `security`, `feature gap`
### v2 monetization gate does not match the selected premium-access intent

**Evidence**

- `AGENT.md` says free users should be blocked from the top 10 by `trending_up_score` or `pucklogic_trends_score`.
- `docs/v2-backend.md` strips only `signals_json` and sets `paywalled = True`.
- `docs/v2-frontend.md` still displays player identity and high-level scoring while hiding detailed explainability.

**Why this matters**

If the product intent is to hide the top-10 premium opportunities, exposing names and scores still leaks the core premium value. That undermines monetization and makes the gate easy to route around socially.

**Canonical direction**

Document exactly what is hidden for free users:

- list rows
- rank positions
- player names
- modal contents
- sort order
- exports
- API fields

If the intent is to hide top-10 value rather than just explainability, current docs are too permissive.

**Suggested implementation standard**

For paywalled top-10 rows, return redacted identity and score fields, and ensure sort order or placeholders do not leak rank/value indirectly.

---

### 10. Medium — `design`, `implementation`
### Season and time semantics are underspecified

**Evidence**

- `docs/v2-backend.md` `is_preseason()` checks only the current calendar month.
- `docs/v2-frontend.md` `isInSeason()` also checks only the current month.
- Other docs use selected `season` strings like `2024-25` and `2026-27`, implying users can inspect historical or future seasons.

**Why this matters**

Month-based helpers work only for “current season, current date” views. They break down for archived analysis, preseason testing, and simulations. This is likely to create subtle bugs in score blending, polling, and UI labels.

**Canonical direction**

Define season-phase logic from explicit season context, not wall-clock month alone.

**Suggested implementation standard**

Add a canonical season metadata helper that determines:

- preseason window for a selected season
- in-season window for a selected season
- whether polling should be enabled
- which Layer 1/Layer 2 blend applies

---

### 11. Medium — `implementation`, `feature gap`
### The ML and ingestion plan still has operational gaps that need explicit ownership

**Evidence**

- `AGENT.md`, `docs/phase-3-backend.md`, and `docs/specs/007-feature-engineering-spec.md` require 10+ seasons of historical data.
- The docs describe ongoing scrapers, but the initial bulk backfill is not scheduled as a first-class implementation stream.
- `docs/pucklogic_architecture_v2.md` says unmatched players should surface in an admin dashboard, but the phase docs do not define that workflow.
- Alias curation, historical reconciliation, and data-quality review are implied but not assigned concrete deliverables.

**Why this matters**

ML projects fail more often on data operations than on model code. The model plan is strong, but the operational layer still depends on implied work that has not been turned into actual implementation scope.

**Canonical direction**

Add explicit deliverables for:

- historical backfill jobs
- alias review/admin workflow
- data-quality checks and thresholds
- season-over-season retraining readiness checks

---

## Canonical Interfaces and Types to Normalize

### Schema and Data Model

| Topic | Recommended canonical direction |
|---|---|
| `season` | Use `TEXT` in canonical NHL format like `2026-27` everywhere externally and in core tables |
| `player_rankings` source identity | Use `source_id UUID REFERENCES sources(id)` |
| `user_kits` | Support `user_id OR session_token`, `source_weights`, `league_format`, and one clearly defined scoring representation |
| scoring configuration | Either `scoring_config_id` or inline `scoring_settings`; if both exist, document precedence and ownership |
| `player_trends` | Store trend scores, confidence, and explainability only |
| `player_projections` | Store per-category projections separately |
| player identity | Store `date_of_birth`; compute `age` for responses |

### API Surface

| Area | Recommended canonical direction |
|---|---|
| Rankings | One endpoint family, ideally either compute-on-demand `POST /api/rankings/compute` or resource-style `GET /api/rankings`, not both |
| Trends | One list endpoint plus clearly scoped detail endpoints if needed |
| Billing | One canonical checkout route, one webhook route, one `GET /api/subscriptions/me` route |
| Draft | One canonical session-creation route and one WebSocket contract |
| Exports | Choose synchronous generate-and-return or async job/status/download flow, then document only that flow |

### Extension Protocol

| Topic | Recommended canonical direction |
|---|---|
| Pick message | Define one payload shape and make all frontend/backend docs use it |
| Player resolution | Decide whether resolution happens client-side or backend-side |
| WebSocket auth | Replace JWT query param with short-lived ticket |
| Session handoff | Define validated `postMessage` bridge with origin, schema, nonce, and expiry rules |
| Reconnect | Define state recovery contract explicitly |

## Action Items

### Priority 0 — Blockers to resolve before more feature implementation

- Create a canonical schema document and mark it as authoritative for all shared tables and core enums.
- Create a canonical API contract document covering rankings, trends, billing, subscriptions, draft sessions, exports, and extension WebSocket messages.
- Decide whether user-owned data is enforced primarily by RLS or by API-layer authorization when using Supabase service-role access.

### Priority 1 — Billing and entitlement remediation

- Define the canonical subscription checkout flow, including which server creates Stripe sessions and how authenticated user identity is attached.
- Add an explicit Stripe-to-user mapping strategy using `client_reference_id` or metadata and persist that mapping in the subscription model.
- Define a canonical `GET /api/subscriptions/me` route and response shape.
- Standardize Stripe route names across all docs and remove deprecated alternates.
- Update the review source docs so the frontend billing flow and backend webhook flow describe the same system.

### Priority 1 — Phase 4 contract and security remediation

- Publish one extension protocol spec with canonical payloads for `pick`, `undo_pick`, `get_suggestions`, reconnect, and state recovery.
- Decide where player-name-to-player-id resolution occurs and document the exact fallback path for manual entry.
- Replace WebSocket JWT query-param auth with a short-lived draft ticket flow.
- Define the web-to-extension session handoff receiver, including origin validation, payload schema validation, nonce/replay protection, and ticket expiry.
- Minimize extension credential storage and document rotation/cleanup rules for any stored session artifacts.

### Priority 1 — Anonymous kits and persistence model

- Specify whether anonymous users can create kits directly in v1 and which routes are available before auth.
- Define how the session token is issued, stored, validated, and migrated on login/signup.
- Define the cleanup mechanism for expired anonymous kits and assign it to a concrete job runner.
- Update RLS and backend access examples so they support the chosen anonymous-kit design consistently.

### Priority 2 — Scope and product contract cleanup

- Mark v1 launch scope explicitly as skaters-only or expand the schema plan to support goalies intentionally.
- Decide whether Phase 4 launch is ESPN-only or ESPN-plus-Yahoo, then move the non-launch platform to backlog if needed.
- Choose popup or sidebar as the primary Phase 4 extension UI and remove conflicting architecture descriptions.
- Define exact free-tier redaction behavior for v2 trends, including list rows, modal content, scores, names, exports, and API fields.

### Priority 2 — Data and ML operations readiness

- Add a first-class historical backfill workstream for 10+ seasons of data required by Phase 3.
- Specify the unmatched-player admin workflow, including review queue ownership and alias curation rules.
- Define data-quality gates for ingestion and model-training readiness.
- Add season-aware helpers that derive phase and blend rules from the selected season rather than the current month alone.

### Priority 3 — Documentation maintenance

- Update or archive `docs/claude-code-reference.md` where it conflicts with the phase and architecture docs.
- Remove outdated route names, field names, and schema examples from earlier phase docs after the canonical contract is chosen.
- Add “source of truth” notes at the top of any doc that intentionally summarizes rather than defines the canonical contract.

## Recommended Next Actions

1. Freeze one canonical schema and route map, then update or archive every conflicting doc before more implementation starts.
2. Resolve the payment and subscription architecture end to end, including authenticated checkout creation, webhook-to-user mapping, and `/api/subscriptions/me`.
3. Rewrite the Phase 4 extension contract as a single protocol spec covering message payloads, auth, reconnect, and page-to-extension session handoff.
4. Decide whether user-owned tables are protected primarily by RLS or by API-layer ownership checks when using the service role, then document and test that model consistently.
5. Either fully specify anonymous kit support or remove it from v1 scope immediately to avoid building against contradictory assumptions.
6. Add an operations plan for historical backfill, alias review, and data quality gates before treating Phase 3 as implementation-ready.

## Notion Task Board Findings (MCP Review)

The task board was reviewed through the Notion MCP server (`PuckLogic Task Board`, data source `collection://753d7997-feb7-45c6-9199-72fdff385da3`). The issues below are specifically about task quality for agent guidance.

### 1. High — `implementation`, `documentation drift`
### Duplicate and conflicting task cards

- Duplicate historical-data card with conflicting scope:
  - `Collect historical NHL data (10+ seasons, 2008–2022)` (`https://www.notion.so/320488853275816eacb1e275baff9ff6`)
  - `Collect historical NHL data (10+ seasons, 2008-2025)` (`https://www.notion.so/3204888532758165ae58ca6b2397a0ad`)
- Duplicate Trends dashboard card:
  - `Build Trends dashboard tab (breakout candidates, regression watchlist)` (`https://www.notion.so/32048885327581c5b5f5e9e0b8d9c381`)
  - `Build Trends dashboard tab (breakout candidates, regression watchlist)` (`https://www.notion.so/32048885327581c49703f0d7e8a8ed7c`)
- Near-duplicate ML integration cards with overlapping intent:
  - `Integrate ML model into FastAPI and set up nightly re-scoring` (`https://www.notion.so/3204888532758164b226ce126e1c8645`)
  - `Integrate ML Trends scores into FastAPI and Supabase` (`https://www.notion.so/32048885327581e0abebc22be7d7b5cd`)

**Problem for Claude Code**

Agent execution can branch into stale or duplicate work, producing conflicting implementations and duplicate PRs.

**Task-board action**

- Merge duplicates and keep one canonical card per capability.
- Add an explicit `Replaced By` or `Supersedes` relation for archived cards.
- Add a uniqueness convention to titles (for example: one canonical card per `{phase + capability + surface}`).

### 2. High — `design`, `feature gap`
### Task scope conflicts with launch scope decisions

- Board includes Yahoo-specific implementation cards (for example, `Build Yahoo Fantasy DOM adapter and selector mapping`) while the core launch path in current implementation docs is ESPN-first.
- Board includes both skater-only and broader-model assumptions across cards, which conflicts with unresolved goalie scope boundaries.

**Problem for Claude Code**

Agents cannot reliably infer whether to implement launch scope or backlog scope, leading to out-of-sequence feature work.

**Task-board action**

- Add an explicit `Launch Scope` property (`v1`, `post-launch`, `experimental`).
- Mark non-launch cards as blocked by launch completion milestones.
- Keep one explicit scope sentence at the top of each card.

### 3. High — `implementation`
### Several cards are epics disguised as single implementation tasks

- Example: `Integrate Stripe Checkout for export purchases` includes pricing strategy, checkout UX, webhook processing, asynchronous export execution, storage TTL, and user notification in one card.
- Example: `Beta test extension with 10–20 real users in mock drafts` bundles recruiting, test ops, triage, quality gates, and launch readiness.

**Problem for Claude Code**

Single-ticket execution is ambiguous and hard to test incrementally; acceptance criteria are too broad for deterministic agent runs.

**Task-board action**

- Split large cards into execution-sized tickets with one primary deliverable each.
- Add `Depends On` links and milestone grouping.
- Require each implementation card to map to one testable API/UI boundary.

### 4. Medium — `implementation`, `design`
### Missing context fields reduce task grounding

- `Architecture Link` is blank in sampled cards despite being required by schema.
- `Assigned` is frequently empty in sampled cards.

**Problem for Claude Code**

Without a precise architecture anchor, the agent may default to non-canonical docs and repeat known contradictions.

**Task-board action**

- Make `Architecture Link` required before status can move to `In Progress`.
- Add a required `Canonical Docs` checklist item with exact file paths.
- Require `Assigned` or `Execution Owner` for any non-backlog card.

### 5. Medium — `implementation`
### Acceptance criteria are often not machine-verifiable

- Many cards describe outcomes but not exact implementation contracts (target files, endpoints, schemas, test commands, and expected response shape).
- Criteria often mix product requirements and implementation notes without explicit pass/fail checks.

**Problem for Claude Code**

Agent output quality depends on deterministic acceptance gates; ambiguous criteria increase rework and review churn.

**Task-board action**

- Add a `Definition of Done` block template to every card:
  - `Files/Modules`
  - `Interfaces Changed`
  - `Tests Added`
  - `Verification Commands`
  - `Non-Goals`

### 6. Medium — `design`
### Priority and estimation quality are inconsistent

- Multiple cards marked `P0 - Blocks launch` even when they overlap or represent alternative scope paths.
- Some large cards have very low hour estimates relative to acceptance criteria breadth.

**Problem for Claude Code**

Priority inflation reduces triage value and causes agents to work on parallel P0s without clear dependency order.

**Task-board action**

- Enforce a cap on active P0 cards.
- Add a lightweight sizing rubric (`S`, `M`, `L`, `XL`) plus estimate confidence.
- Require dependency ordering before setting `P0`.

## Task Board Remediation Checklist

1. Deduplicate conflicting cards and archive superseded versions.
2. Add `Launch Scope`, `Depends On`, and `Replaced By` properties to the database.
3. Require `Architecture Link` and `Canonical Docs` before `In Progress`.
4. Split epic-sized cards into execution-sized implementation tickets.
5. Normalize `Definition of Done` to machine-verifiable checks for agent runs.
6. Re-baseline `P0` assignments and estimates after dependency mapping.

## Clarifying Questions

1. For v1, should anonymous visitors be able to save and revisit kits before signing in, or is anonymous support limited to a single browser session only?
2. Should Phase 4 launch with ESPN only, or should Yahoo support be treated as a same-phase requirement rather than backlog?
3. For the v2 paywall, should free users see placeholder rows for the premium top 10, or should those rows disappear entirely from rankings and modal flows?
