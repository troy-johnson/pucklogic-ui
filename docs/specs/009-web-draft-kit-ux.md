# 2026-04-05 — Web-First Draft Kit UX Spec

**Status:** Approved  
**Milestone:** B — Lock the draft kit workflow / UI scope  
**Priority:** Launch-shaping  
**Risk:** High  
**Supersedes:** UX planning detail previously embedded in `docs/plans/008a-draft-season-readiness.md`  
**Related:** `docs/specs/008-live-draft-sync-launch-required.md`, `docs/research/002-web-draft-kit-ux-brainstorm.md`, `docs/plans/008a-draft-season-readiness.md`, `docs/adrs/007-web-first-draft-session-and-temp-kit-lifecycle.md`

## Architecture References

- `docs/pucklogic-architecture.md`
- `docs/frontend-reference.md`
- `docs/backend-reference.md`
- `docs/extension-reference.md`
- `docs/specs/008-live-draft-sync-launch-required.md`
- `docs/plans/008a-draft-season-readiness.md`

## Why this spec exists

Milestone B needs a canonical UX contract for the web product before implementation starts. The milestone plan should track scope and sequencing, but this spec should define the actual launch UX: primary user workflow, required screens, wireframe priorities, design-system primitives, and the critical UI states that implementation must honor.

This spec is intentionally web-first. Live draft sync remains launch-required, but extension UX is treated as a later integration surface rather than the primary planning driver.

## Goals

- Define the end-to-end launch workflow for the web app
- Define the launch-worthy screen inventory for pages, overlays, and major states
- Define which surfaces need wireframes first and at what fidelity
- Define a minimal design-system foundation for implementation consistency
- Define critical state models the UI must represent clearly
- Surface open product decisions before implementation begins

## Non-Goals

- Deep extension implementation planning
- Yahoo-specific UX specialization beyond preserving future compatibility
- Post-launch UX optimization work that does not shape launch information architecture
- Detailed component implementation tasks or engineering estimates

## Surface responsibilities

This spec covers **web UI only**. Extension implementation is deferred to Milestone I and will be specified separately.

### Web UI responsibilities (in scope)

- All pre-draft prep surfaces: dashboard, kit library, league profile, rankings workspace
- Session initiation from the web app
- Live draft session page: session status display, rankings table, suggestion list, kit switching
- Manual pick entry form (user-initiated, available whenever sync is unavailable or degraded)
- Reconnect prompt and guided recovery flow (surfaced when backend session state requires reconciliation)
- Sync health status indicators (`connected`, `reconnecting`, `disconnected`, `manual`, `out-of-sync`) — driven by backend session state, not by extension presence
- Session end and post-draft summary

### Extension responsibilities (out of scope — Milestone I)

- Draft room detection and sync initiation — **ESPN is the launch-critical platform; Yahoo ships at Milestone I only if it does not jeopardize ESPN stability (per spec 008 §D5)**
- Pick extraction from platform DOM
- Automatic pick ingestion into backend session state
- Auto-reversion from manual mode when sync recovers (with user notification)
- Token consumption prompt on draft room entry
- Extension sidebar and popup UI

### How they connect

The web UI reads and displays backend session state. The extension writes to that same backend state. The web UI must function without the extension installed — extension integration is additive, not required for web UI operation.

---

## Planning split recommendation

This work should be reviewed as three linked subareas inside one spec:

1. **UX workflow/spec planning** — journeys, state transitions, launch boundaries
2. **Screen/wireframe planning** — screen inventory, wireframe order, fidelity level
3. **Design-system planning** — reusable web primitives and feedback/state patterns

## Assumptions and boundaries

### Assumptions

- Web is the primary launch surface for draft kit creation, saved kits, rankings, export, and live draft session control
- Authenticated accounts and saved kits are required launch scope
- Live draft sync is required at launch
- Backend draft session state is authoritative
- Manual pick entry is a launch-required fallback, not an optional enhancement
- Anonymous users may explore with temporary browser-scoped work before authenticating

### In scope

- Web onboarding, authenticated return flow, kit selection/creation, draft prep, live draft session UX, reconnect, and manual fallback
- Launch-worthy screen inventory and interaction states
- Wireframe sequencing and design-system foundation

### Out of scope

- Deep extension workflow design
- Platform-specific extension UX beyond future-safe constraints
- Post-launch optimizations unless they materially affect launch structure

## Primary launch workflow

### Recommended v1 primary flow

1. Land on marketing/home page and understand value proposition
2. Create account or continue anonymously for limited exploration
3. Create a temporary kit or select an existing saved kit if authenticated
4. Review default rankings, then progressively add league profile and scoring context
5. Save progress to account when ready for durable prep
6. Review rankings and suggestions in the pre-draft workspace
7. Export/print from the pre-draft workspace once auth and prep-readiness gates are satisfied
8. Start a live draft session from the web app (extension connects and begins syncing picks independently — Milestone I)
9. Monitor session status, rankings, and suggested best available players on the live draft screen
10. Enter picks manually if sync is unavailable or degraded; session continues without interruption
11. If disconnected, reconnect and reconcile authoritative session state from the web app
12. End session and return to saved kit context

## Primary user journeys

### 1. First-time user onboarding

- Visitor lands on homepage
- Sees concise explanation: rankings + saved kits + live draft support
- Chooses sign up / sign in / limited anonymous exploration
- If exploring anonymously, sees lightweight persistent temporary-work status and contextual reminders that login is required to save, export, or start live draft
- On first authenticated entry, receives short onboarding checklist:
  - create first kit
  - create/select league profile
  - review rankings
  - save and start draft prep
- Success condition: user reaches a prepared pre-draft workspace with at least one saved kit

### 2. Returning authenticated user

- User lands on dashboard
- Sees recent kits, recent league profiles, last draft session status, and next recommended action
- Can resume prep, open an existing kit, or reconnect to an interrupted session
- Success condition: user reaches intended work area in 1–2 clicks

### 3. Creating/selecting a draft kit

- User opens kit library from dashboard or rankings workspace
- If anonymous, user creates a temporary kit tied to browser/session state
- If no saved kits exist, guided empty state drives first-kit creation
- If one kit exists, make it the default working context while preserving easy edit/duplicate actions
- If multiple kits exist, support search/sort/select/duplicate/delete/rename flows
- Success condition: exactly one active kit is in context for rankings and live session launch

### 4. Preparing for a draft

- User starts with an active kit and default rankings even before league profile is complete
- User progressively adds league profile + scoring context as prep becomes more serious
- User lands in pre-draft workspace with rankings table, top suggestions, and setup warnings if needed
- User can edit source weights, save changes, and validate that rankings have refreshed — the table enters skeleton state during recompute, then repopulates with an "Updated just now" timestamp and a "Rankings updated" toast on completion
- Success condition: prep is complete enough to start a live session confidently

### 5. Starting a live draft session from the web app

- User clicks start draft session from prep workspace
- If anonymous, user is gated to auth before launch can continue
- Launch flow confirms league/profile, active kit, and that no other active live session is currently owned by the user
- Session is created in backend; extension connects independently to begin syncing picks (Milestone I)
- User enters live draft screen showing session status sourced from backend state
- Web UI displays sync health indicators and manual fallback affordances regardless of whether the extension is active
- Success condition: user can begin the draft from the web UI; sync state is visible and fallback is always available

### 6. Drafting with rankings/suggestions

- Live draft screen shows available-player rankings, a primary recommendation list, roster-context signals, recent picks, and session status
- User can inspect suggestion rationale without losing draft position awareness
- Deeper rationale is guaranteed for the decision-relevant player cohort; if implementation lift is negligible, rationale may be available for all players
- Rankings and suggestions refresh after authoritative pick updates
- **Kit changes are allowed during a live session.** Switching the active kit triggers a rankings recompute: table enters skeleton state, then repopulates with updated rankings, and a toast confirms "Rankings updated." The session's `kit_id` is updated in the backend. The user should see a clear visual signal distinguishing a kit-change refresh from a pick-driven refresh.
- Success condition: user can make the next pick decision from one screen without context switching

### 7. Manual pick entry fallback

- If sync confidence drops or automation is unavailable, user enters manual mode from an inline alert or action bar
- User searches player, records drafted team/pick, and immediately sees rankings/session state reconcile
- Manual mode is reversible: when backend session state reports sync health restored, the web UI surfaces a prompt to return to sync mode
- Sync recovery detection is an extension responsibility (Milestone I); the web UI reacts to the resulting backend state update
- Success condition: draft can continue without abandoning the live session UX

### 8. Reconnect flow

- On refresh, tab close/reopen, or transient disconnect, user returns to a reconnecting state
- App requests authoritative `sync_state` and shows last known session timestamp/status
- If reconciliation succeeds, user resumes in place and sees confirmation that the session state was restored
- If reconciliation fails, authenticated users get a guided reconnect option first, then manual mode, then end-session escape hatch
- Success condition: no ambiguity about whether displayed draft state is trusted, stale, or recovered

## Draft pass model

**User-facing term:** draft pass / draft passes  
**Internal/backend term:** session token (`draft_tokens` table, `draft_sessions` record)

> **v2 naming note:** When in-season recommendations ship, a "season pass" product will need a distinct name to avoid confusion with draft passes. Resolve before v2 goes to market.

### Draft pass balance display

- Pass balance is persistently visible in the authenticated app shell (header or nav) whenever the user has one or more passes ("2 draft passes remaining")
- Zero-pass state shows a prompt to purchase rather than hiding the indicator
- Balance updates immediately after a successful Stripe purchase

### Starting a session — draft pass states

**User has passes available:**
1. User clicks "Start draft session" from prep workspace or live draft nav
2. Start session modal confirms: active kit, league profile, platform target, passes remaining
3. User confirms → pass consumed (session token created in backend) → `draft_sessions` record created → user enters live draft screen

**User has no passes:**
1. Start session is available in the UI but leads to a payment gate, not a blocked state
2. Payment gate explains what a draft pass includes and links to Stripe Checkout
3. After successful purchase, user returns to the session start flow with pass available

**User is anonymous:**
1. Start session is gated to auth first, then payment if no pass exists
2. Auth gate explains that purchasing a draft pass requires an account

### Single-session rule and conflict behavior

- One active live draft session per user is enforced at launch
- If a user attempts to start a new session while one is already active, the start flow is blocked
- The user sees a prompt: *"You already have an active draft session. Resume it or end it before starting a new one."* with two explicit actions: **Resume active session** / **End active session**
- Silent takeover is not permitted — no session is replaced without explicit user confirmation
- Multi-device behavior follows the same rule: any device may reconnect to the active session via the standard reconnect flow, but no device may start a second session while one is active
- No pass is consumed for a blocked session start attempt

### Pass consumption confirmation

- The pass is consumed at the moment the user confirms session start — not at purchase time and not at draft room entry (for web-initiated sessions)
- Confirmation step must clearly state "This will use 1 of your X remaining draft passes"
- If the user exits the start flow before confirming, no pass is consumed

### Milestone I extension behaviour (not web UI scope)

- Extension detects draft room entry and surfaces its own pass consumption prompt in the sidebar
- Extension prompt mirrors the web confirmation: "Use PuckLogic for this draft? X draft passes remaining"
- If no pass is available, extension links to web app purchase flow
- Pass consumption via extension uses the same backend path as web-initiated sessions

## Authentication and temporary-work policy

### Anonymous exploration

- Anonymous users may create a temporary kit, customize source weights, and view their custom rankings — all browser-scoped
- Anonymous users may not create durable saved kits, export/print, or start a live draft session
- Anonymous state must be visibly temporary through both persistent lightweight status and contextual auth-gate messaging
- The kit editor must display a persistent label before customization begins: "Working in temporary session — kit pass required to save"
- The save gate copy should frame the kit pass as value gained, not access restricted: "Your custom rankings are ready — save them with a kit pass to use across devices and in your live draft"

### Temporary-kit lifecycle

- Temporary kits are tied to the browser/session token
- Temporary kits are **directly resumable for 24 hours based on last activity** — the product must track `last_activity_at` to support this
- **Activity definition:** only write actions update `last_activity_at` — changes to source weights, league profile selection, or kit name. Viewing rankings or loading the page does not count.
- After the 24-hour direct-resume window, recovery requires normal sign-in (kit is still accessible, but not auto-resumed)
- **UI state for 24h–7d window:** a persistent banner appears in the kit context: *"Your temporary work is saved in this browser. Sign in to save it permanently before it expires."* with a days-remaining indicator and a sign-in CTA
- **Temporary kits are permanently deleted 7 days from `created_at`** — this is enforced by a nightly cron cleanup job; there is no recovery path after this point
- The 7-day window is `created_at`-based, not `last_activity`-based; interacting with the kit does not extend the cleanup deadline
- **Post-expiry state:** if a user returns after the 7-day cleanup, the temporary kit is gone; show an empty state with *"Your temporary session has expired"* and a CTA to start fresh or sign in to access saved kits
- After authentication within the 7-day window, temporary kit ownership migrates to the user account
- After recovery or mid-flow auth migration, the UI should show a confirmation toast/banner that the temporary work has been restored to the account

### Durable actions that require auth

- Save kit to account
- View prior saved kits across sessions/devices
- Export/print rankings
- Start a live draft session

## Default rankings

Default rankings are shown to all users — anonymous and authenticated — without requiring any setup. They are the entry-point experience for the free tier and the fallback state when no kit or league profile is active.

### What default rankings are built from

- PuckLogic's own projection aggregation using all active public sources at equal weight
- A standard preset scoring configuration (ESPN standard H2H as the baseline)
- A default league profile assumption (10 teams, standard roster slots)
- All skaters included — no player count cutoff

### When default rankings are shown

- Anonymous user arrives and begins exploring
- Authenticated user has no saved kit or league profile yet
- Authenticated user on free tier (no kit pass) without an active temporary custom kit session — shown default rankings
- Kit pass holder who has not yet configured a kit or league profile

### How the UI represents default rankings

- A visible label indicates rankings are using preset defaults (e.g. "Default settings — customize for your league")
- Users on the free tier see a persistent prompt explaining that a kit pass unlocks saving their customization across devices and sessions
- When a kit pass holder saves a kit and league profile, rankings recompute against their specific context and the default label clears
- Switching back to no active kit restores default rankings — no empty/error state

### What default rankings are not

- Default rankings are not a degraded or error state — they are a first-class product experience
- The "rankings empty state (setup incomplete)" view state applies only when a user is mid-setup with a partial configuration, not on first visit

## Payment model

### Tiers

**Free tier**
- Default rankings for all players using preset source weights and preset scoring configuration
- Source weight customization is available in a temporary browser-scoped session — work is visible immediately but cannot be saved to account without a kit pass
- No saved kits, no export, no live draft
- Available to anonymous and authenticated users
- The kit editor must display a persistent label indicating the session is temporary ("Working in temporary session — kit pass required to save") before the user invests time customizing

**Kit pass (paid — one-time seasonal purchase)**
- Custom source weights and saved kits
- Export/print (included; not pay-per-file for kit pass holders)
- Required for any personalized prep work beyond default rankings
- Pricing: **$4.99 one-time**

**Draft passes (paid — $2.99 per pass)**
- Required to start a live draft session; user-facing name is "draft pass"
- Purchased in advance via Stripe Checkout on the web app; passes sit in account until consumed
- Consuming a pass creates a `draft_sessions` record (internal: session token)
- Pass balance is visible in the web app header and (Milestone I) in the extension popup
- Pass packs (e.g. 5 passes at a discount) are a post-launch consideration

### Draft pass consumption model

- Passes are purchased independently of session start — users may hold a balance
- A session is started from the web app or (Milestone I) triggered by extension draft room detection
- At session start the user confirms before the pass is consumed
- Unused passes persist in the account indefinitely

### Payment gates in the UI

| Action | Gate |
|---|---|
| View default rankings | None |
| Customize source weights (temporary, browser-scoped) | None |
| Save customized kit to account | Kit pass required |
| Export / print rankings | Kit pass required |
| Start a live draft session | Auth + draft pass required |

### Pricing resolution

- Kit pass ($4.99 one-time) and draft passes ($2.99/session) are sold **separately**
- Users buy what they need independently; no bundle required at launch
- The extension requires a draft pass to function; the kit pass alone does not unlock live draft
- A bundle SKU may be considered post-launch if conversion data supports it

### Entitlement resolution

Spec 008 open question #2 ("Is paid entitlement enforced at launch?") is resolved: draft passes are required to start a live draft session at launch. Spec 008 §D6 has been updated to remove the conditional "if paid entitlement is enforced" language.

## Export and prep-readiness policy

- Export/print belongs in the pre-draft workspace, not a separate export funnel
- Export is available only when:
  - the user is authenticated
  - the user holds a kit pass
  - an active kit is selected
  - the league profile is complete enough for rankings
  - rankings are in a valid computed state

### Valid computed state

The UI may treat rankings as export-ready only when:

- the latest ranking request completed without error
- the current result set is non-empty
- the rendered rankings match the current active kit + league profile context
- the view is not stale, not loading, and not in an error state
- no blocking setup omissions remain

## Screen inventory

### Launch-required pages

- Marketing / landing page
- Sign up page
- Sign in page
- Password reset / recovery page
- Auth callback / account linking transition page
- Authenticated dashboard / home
- Kit library page
- Kit create/edit page or dedicated kit editor workspace
- League profile list page
- League profile create/edit page
- Pre-draft workspace / rankings page
- Live draft session page
- Session summary / post-draft return page (final roster by position, pick log with round/pick number, PuckLogic ranking vs actual pick position per player, undrafted top suggestions, roster completeness check, link back to saved kit)
- Account/settings page

### Launch-required overlays and subviews

- Create kit modal or drawer
- Rename / duplicate / delete kit modal
- Create league profile modal or drawer
- Start live draft session modal
- Suggestion detail drawer
- Player detail drawer
- Manual pick entry modal or drawer
- Reconnect modal
- Unsaved changes confirmation modal
- Session end confirmation modal
- Auth-required gate modal for anonymous users reaching save/live actions
- Auth-required gate modal for anonymous users reaching export actions

### Launch-required view states

- Unauthenticated marketing state
- Authenticated dashboard with no kits
- Authenticated dashboard with one kit
- Authenticated dashboard with multiple kits
- Rankings empty state (setup incomplete)
- Rankings loading state
- Rankings populated state
- Rankings error state
- Rankings out-of-sync warning state
- Temporary anonymous kit state
- Export blocked / prep incomplete state
- Live draft connected state
- Live draft reconnecting state
- Live draft disconnected/manual-fallback suggested state
- Live draft manual mode active state
- Live draft error/blocking state
- Session reconnect available state
- Saved success/toast state for kits/profile changes
- Draft pass balance state (has passes)
- Draft pass zero-balance / purchase prompt state

## Wireframe list

### Wireframe first

- **Authenticated dashboard** — medium fidelity
- **Kit library + create/edit flow** — medium fidelity
- **Pre-draft workspace / rankings screen** — high fidelity
- **Start live draft session modal** — medium fidelity
- **Live draft session screen** — high fidelity
- **Auth gate for save/export/live draft actions** — medium fidelity
- **Manual pick entry flow** — medium fidelity
- **Reconnect state** — medium fidelity

### Wireframe second

- **Landing page** — low to medium fidelity
- **Sign up / sign in / password reset** — low fidelity unless custom auth UX is substantial
- **League profile create/edit flow** — medium fidelity
- **Temporary-kit recovery after sign-in** — medium fidelity
- **Player detail drawer** — low to medium fidelity
- **Suggestion rationale drawer** — medium fidelity
- **Session summary screen** — medium fidelity
- **Account/settings page** — low fidelity

### Fidelity rationale

- **Low fidelity** for standard or low-risk flows where hierarchy matters more than polish
- **Medium fidelity** for forms, library management, and modal/drawer interaction flows
- **High fidelity** for dense decision surfaces where table layout, status treatment, and interaction rhythm materially shape implementation

## Design-system foundation

### Typography

- Clear 3-tier hierarchy: page title, section title, supporting label/meta text
- Dense-data surfaces should prioritize tabular readability over marketing expressiveness
- Numeric/stat columns need tabular numeral support

### Spacing and layout

- 4/8px spacing system with predictable density ramps
- Two primary layout modes:
  - marketing/account pages with centered content rails
  - app workspace pages with multi-panel responsive shell
- Standard workspace shell: top app bar + optional left navigation + primary content + right contextual drawer

### Navigation model

- Global nav: Dashboard, Kits, League Profiles, Rankings, Live Draft, Account
- Contextual subnav inside prep/live flows where needed
- Persist active kit and active league context visibly in the app shell
- Persist temporary-versus-saved status visibly in the app shell when unauthenticated
- Persist draft pass balance visibly in the app shell for authenticated users ("X draft passes remaining"); zero-pass state shows a purchase prompt rather than hiding the indicator

### Data presentation primitives

- Rankings table with sticky header, sortable columns, filter/search affordances, row selection, and dense/comfortable density options
- Card primitives for dashboard summaries, kit summaries, and session summary blocks
- Drawers for non-destructive deep dives (player detail, suggestion rationale)
- Modals for confirmations and short completion flows

### Status and feedback primitives

- Status chips for: saved/unsaved, temporary/account-saved, connected/reconnecting/disconnected, sync healthy/out-of-sync, live/manual, draft ready/setup incomplete
- Alert patterns:
  - inline informational banner
  - warning banner with primary recovery action
  - blocking error panel for session-critical failures
- Toasts for lightweight success feedback; avoid toasts for critical sync state

### Empty / loading / error patterns

- Empty states must always include next best action
- Loading states should preserve layout skeletons on tables/cards instead of blank screens
- Rankings recompute (triggered by source weight save or kit change) uses skeleton state → repopulated table → "Updated just now" timestamp + "Rankings updated" toast; toast is suppressed on page load and background refreshes
- Error states should distinguish retryable failures from setup blockers
- Out-of-sync states need explicit copy about authoritative backend reconciliation

### Draft-state indicators

- Persistent session badge in header
- Persistent temporary-work badge for anonymous users
- Last sync timestamp
- Connection health indicator
- Manual mode badge when active
- Unsaved kit changes indicator in prep contexts
- Draft progress summary: current pick, recent picks, roster needs snapshot

## Critical UI state models

### Authentication

- Unauthenticated visitor
- Anonymous explorer with temporary kit
- Authenticated user with migrated anonymous data
- Authenticated user with no existing data

### Saved kit inventory

- No saved kit
- One saved kit
- Multiple saved kits

### Draft lifecycle

- Pre-draft
- Live draft active
- Paused or disconnected
- Manual fallback active
- Session ended / archived

### Rankings data state

- No rankings yet
- Loading/recomputing
- Populated and healthy
- Error retrieving/computing
- Out-of-sync with live session context

### Save and edit state

- Clean / saved
- Dirty / unsaved
- Saving
- Save failed / retry needed

### Temporary work state

- Temporary and directly resumable (< 24h since last activity, based on `last_activity_at`)
- Temporary and login-gated for recovery (24h–7d since `created_at`)
- Temporary and permanently expired (> 7 days since `created_at` — cron-deleted, not recoverable)
- Migrating to authenticated account
- Restored to authenticated account

## Must-have vs post-launch cut line

### Must-have for launch

- Authenticated dashboard
- Saved kits CRUD sufficient for real use
- League profile selection/creation sufficient for rankings context
- Pre-draft rankings workspace
- Temporary anonymous exploration with clear auth gates
- Live draft session screen with clear sync status
- Manual pick entry fallback
- Reconnect recovery flow
- Basic suggestion rationale visibility
- Export/print inside prep workspace with explicit readiness gating

### Post-launch / cuttable if schedule tightens

- Advanced onboarding tours
- Rich comparative visualizations beyond core rankings/suggestions
- Deep customization of workspace layout
- Extensive draft history analytics
- Multi-platform UX specialization beyond what is required to preserve web-first information architecture

## Web UI constraints for future extension compatibility

The web UI must be built in a way that allows extension integration in Milestone I without redesigning core state models. These are web UI requirements, not extension implementation notes.

- Web live draft session UX must not assume extension presence in the primary happy path
- Session status model should be reusable by extension integration later (`connected`, `reconnecting`, `manual`, `out-of-sync`)
- Start-session language should remain platform-agnostic enough to support extension attachment later without redesigning core state models
- Manual fallback must remain first-class because it de-risks both extension failures and web-only operation
- Temporary-work and auth-gate language should remain compatible with later extension attachment flows

## Proposed default resolutions for remaining open questions

These defaults were reviewed and are the current recommended decisions unless later research or wireframing exposes a stronger alternative.

### 1. Decision-relevant cohort for deeper rationale

**Approved direction:** use a hybrid rule.

- Guarantee deeper rationale for players projected within the **first 50% of the expected drafted-player pool** for the active league profile
- If no league profile exists yet, use a default expected draft pool of **216 total picks** and guarantee deeper rationale for the **top 108 players**
- Extend deeper rationale beyond that cutoff for players who still sit meaningfully above replacement level by VORP if implementation cost is low
- If implementation cost is negligible, deeper rationale may be shown for all players

**Why this default:**
- “Half of an expected draft” maps better to how users think than an arbitrary top-200 rule
- The fallback default stays inside the 10–12 team / 18–20 player-per-team planning range discussed in brainstorm
- A VORP-aware extension preserves useful late availability without making VORP the only rule users must understand

### 2. League-profile completeness for export/readiness gating

**Approved direction:** a league profile is complete enough for export when all of the following are present:

- league size / number of teams
- roster slots by position
- scoring configuration or scoring preset
- active kit selection

**Not required for export gating by default:**
- platform connection details
- live draft session metadata
- optional fine-tuning fields that do not materially change rankings integrity

**Why this default:**
- It protects export usefulness without turning export into a high-friction setup wall
- It matches the idea that export is a serious prep action, but not necessarily a live-session action

### 3. Default UX copy direction for temporary/auth/recovery states

**Approved direction:** keep the same message intent, but use a softer, more welcoming tone in final UX copy.

**Working copy intent:**

- Temporary kit status should communicate that work is saved only in the current browser for now
- Auth gate copy should explain that logging in enables saved kits, cross-device access, export, and live draft
- Recovery copy should confirm that temporary work is now associated with the user account

**Tone guidance:**

- Prefer supportive, low-friction language over hard blocking language
- Explain value gained by logging in, not just what is restricted
- Keep copy plain-language and action-oriented

**Why this direction:**
- It preserves the correct product messaging while allowing wireframes and content polish to find a more conversion-friendly tone

### 4. Saved-kit archive support at launch

**Approved direction:** do **not** require archive at launch.

- Launch should support rename, duplicate, and delete
- Archive can remain post-launch unless wireframes show a clear organizational failure without it

**Why this default:**
- It reduces CRUD complexity while keeping the library usable for launch

## Open product questions

- Finalize polished UX copy in wireframes/content review using the approved softer tone direction
- Confirm whether archive remains unnecessary after wireframe review of the kit library at realistic scale

## Recommended implementation and design order

1. **Workflow/spec first** — lock the canonical v1 journey and cut list
2. **Pre-draft workspace + live draft session wireframes** — highest risk, highest leverage
3. **Dashboard + kit library + temporary-state flows** — establish entry and saved-work model
4. **League profile + export gating flows** — ensure readiness requirements are represented clearly
5. **Manual fallback + reconnect flows** — validate recovery UX before implementation
6. **Design-system primitives** — finalize app shell, table, drawer, chip, alert, and state treatments
7. **Supporting auth/settings/session-summary screens** — complete launch shell around the core workflow

## Tradeoffs considered

### Option A — Single combined planning artifact inside the milestone plan

- **Pros:** faster to author, one document to review
- **Cons:** blurs milestone tracking with canonical UX decisions, weaker handoff to implementation

### Option B — Dedicated spec plus lighter milestone plan tracking

- **Pros:** clearer source of truth, cleaner implementation contract, easier to evolve and review
- **Cons:** slightly more document structure to maintain

**Recommendation:** Option B.

## Reversibility and risk

- Information architecture and primary workflow choices become harder to change after high-fidelity wireframes and implementation begin
- Design-system token choices are moderately reversible
- Live draft screen layout decisions are less reversible because they shape component composition and data contracts
- Temporary anonymous retention/recovery rules are moderately expensive to change once users form expectations around them
- Deferring manual fallback or reconnect UX is high risk because both are launch-required behaviors

## Acceptance criteria

- One agreed web-first v1 workflow exists for launch
- Launch-required screen inventory exists for pages, overlays, and major states
- Wireframe priority and fidelity recommendations exist for core surfaces
- Minimal design-system primitives are defined for implementation consistency
- Must-have vs post-launch cut line is documented
- Decisions from the brainstorm and ADR inputs are reflected in the spec
- The approved hybrid rationale rule, export readiness fields, softer copy direction, and no-archive-at-launch decision are reflected in the spec
- Open product questions blocking implementation are explicitly listed
- Milestone B plan links to this spec instead of duplicating detailed UX content
- Anonymous users cannot export/print rankings, start live draft, or create durable saved kits without authenticating
- Temporary kits migrate to the authenticated user account when a user signs in mid-flow or reclaims work through sign-in
- The product enforces one active live draft session per user at launch
- Manual fallback mode is available from the live draft session when sync confidence drops and is reversible if sync health returns
- Out-of-sync states explicitly communicate that backend session state is authoritative and reconciliation is required
- Payment tier model is defined: free (default rankings + browser-scoped customization), kit pass (saved kits + export), draft passes (live draft sessions)
- Free-tier users may customize source weights in a temporary browser session; saving to account requires a kit pass; the kit editor displays a persistent temporary-session label before customization begins
- Default rankings are defined as a first-class product experience available to all users without setup; they are not a degraded or error state
- Draft pass balance is visible in the authenticated app shell; zero-pass state surfaces a purchase prompt
- Draft passes use the user-facing term "draft pass / draft passes"; internal backend term is session token

## Recommendation

Approve this spec as the canonical web-first UX contract for Milestone B, then execute design and implementation in the recommended order above.

## Follow-on questions after spec approval

- Should the spec later be split again into a dedicated design-system artifact once implementation starts?
- Does export need explicit launch-screen treatment in a follow-on spec, or is current coverage sufficient for Milestone B?
- Does draft history need any launch-visible footprint on dashboard/session summary, or can it remain post-launch?
