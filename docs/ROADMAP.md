# PuckLogic Roadmap

**Launch target:** Mid-September 2026  
**Strategy:** Ship web draft kit first. Extension is conditional — proceeds only if it does not jeopardize the web launch.  
**Current date:** 2026-04-19  
**Solo dev — nights and weekends**

---

## Milestone Status

| Milestone | Window | Status | Key Docs |
|---|---|---|---|
| A — Scraper hardening + backfill | Mar 28 – Apr 12 | In progress | [Plan 008a](plans/008a-draft-season-readiness.md) |
| F — First real ML execution | Apr 13 – Apr 20 | Complete | [Plan 008a §F](plans/008a-draft-season-readiness.md#milestone-f--first-real-ml-execution-run) |
| B — Lock draft kit workflow / UI scope | Apr 21 – May 4 | Approved early | [Spec 009](specs/009-web-draft-kit-ux.md) · [ADR 007](adrs/007-web-first-draft-session-and-temp-kit-lifecycle.md) |
| C — Backend integration verification | May 5 – May 18 | **Complete** | [Spec 011](specs/011-milestone-c-token-pass-backend.md) · [Plan 011a](plans/011a-token-pass-entitlements-and-gating.md) · [Plan 011b](plans/011b-session-close-rankings-snapshot.md) |
| D — Build web draft kit UI | May 19 – Jun 29 | Planned | [Spec 009](specs/009-web-draft-kit-ux.md) |
| E — Polish exports | Jun 30 – Jul 13 | Planned | [Plan 008a §E](plans/008a-draft-season-readiness.md#milestone-e--make-exports-launch-grade) |
| G — Launch hardening | Jul 14 – Aug 17 | Planned | [Plan 008a §G](plans/008a-draft-season-readiness.md#milestone-g--harden-the-web-launch) |
| H — Extension go/no-go | Aug 18 – Aug 24 | Conditional | [Plan 008a §H](plans/008a-draft-season-readiness.md#milestone-h--extension-gono-go) |
| I — Extension MVP / beta | Aug 25 – Sep 14 | Conditional | [Spec 008](specs/008-live-draft-sync-launch-required.md) · [Plan 008a §I](plans/008a-draft-season-readiness.md#milestone-i--extension-mvp--beta-conditional) |

### Current execution reality (2026-05-05)

- `008a` remains a **reference roadmap**, not the literal active execution order.
- `008b` live-draft backend, `008d` draft-pass lifecycle, and `008e` optional pick-number follow-up are **implemented and merged on `main`**.
- `008c` extension sync adapters are implemented; remaining validation is season-blocked live draft-room verification, with Yahoo still gated/non-blocking.
- **Milestone C complete:** `011a` (kit-pass entitlements + Stripe + route gating) and `011b` (session close rankings snapshot) merged on `main` via PR #36 (2026-05-06).
- `010a` web draft kit UI remains **scaffold-only** until spec `010` is approved.
- **Next execution priority:** Milestone D — build web draft kit UI. Spec `010` approval is the gate before full implementation.

Use this roadmap for milestone sequencing and launch prioritization. For live branch/phase status, defer to `docs/state/workflow-state.md` and the active plan docs.

---

## Open Architecture Work

Items identified during Milestone B spec review that need to land in later milestones.

### Milestone B approval (Apr 21 – May 4)
- [x] Approve payment model: default rankings free · kit pass $4.99 one-time · draft passes $2.99/session (sold separately)
- [x] Approve token-based session model (buy passes in advance, consume at draft room entry)
- [x] Approve closed beta feedback pipeline: Discord + structured prompt; user sourcing deferred to Aug 2026

### Milestone C backend additions (May 5 – May 18) — **Complete**
- [x] Implement spec 011 entitlement model on `subscriptions` (kit-pass season + purchase timestamp; no separate `draft_tokens` table)
- [x] Update Stripe checkout/webhook flow for kit-pass product metadata (`user_id`, `product`, `season`) and idempotent crediting
- [x] Expose authenticated `GET /entitlements` for web app and extension entitlement reads
- [x] Kit pass entitlement gating for customization and export paths
- [x] Snapshot PuckLogic rankings into session record at session close — required for post-season "ranking vs. actual performance" ML comparison job (no UI needed; backend only)

### Milestone I extension additions (Aug 25 – Sep 14)
- [ ] Draft room detection → token consumption prompt ("Use PuckLogic for this draft? X sessions remaining")
- [ ] Token balance visible in extension popup
- [ ] Manual session start from extension with explicit token consumption
- [ ] Auto-revert from manual fallback when sync recovers (extension-side, with user notification)

---

## Blocked / Pre-Launch Follow-Ups

### Season-blocked live draft-room verification
- [ ] Manual ESPN live draft-room verification once draft rooms are available next season
- [ ] Manual Yahoo live draft-room verification once draft rooms are available next season
- [ ] Execute the live verification checklist in a real room:
  - [ ] attach/connect succeeds
  - [ ] pick detection reaches backend session correctly
  - [ ] reconnect after interruption restores authoritative state
  - [ ] degraded-state behavior is visible and understandable
  - [ ] manual fallback works without blocking draft use
  - [ ] recovery from manual/degraded state is confirmed

### Backend-owned inactivity-timeout confirmation
- [ ] Confirm the backend config/source of truth for draft-session inactivity timeout
- [ ] Confirm runtime behavior for expired/abandoned draft sessions
- [ ] Confirm client-facing response/handling expectations for expired sessions
- [ ] Reconcile the confirmed timeout contract across backend, extension, plan, and spec docs

### Analytics / metrics follow-up
- [ ] Write a dedicated analytics/telemetry spec covering web app, backend, and extension
- [ ] Define the event taxonomy for live draft sync, reconnect, degraded state, and manual fallback
- [ ] Decide whether telemetry flows through the Python backend as the primary ingest path before any provider fanout
- [ ] Implement production-grade metrics export / observability after the spec is approved

---

## Product Decisions Locked in Milestone B

| Decision | Resolution | Source |
|---|---|---|
| Primary launch surface | Web app (extension conditional) | [ADR 007](adrs/007-web-first-draft-session-and-temp-kit-lifecycle.md) |
| Live draft sync required | Yes — launch gate | [Spec 008](specs/008-live-draft-sync-launch-required.md) |
| Manual fallback required | Yes — launch gate | [Spec 008](specs/008-live-draft-sync-launch-required.md) |
| Auth for saved kits / export / live draft | Required | [ADR 007](adrs/007-web-first-draft-session-and-temp-kit-lifecycle.md) |
| Temp kit direct-resume window | 24h from last activity | [ADR 007](adrs/007-web-first-draft-session-and-temp-kit-lifecycle.md) |
| Temp kit recovery window | Up to 7 days from created_at (cron cleanup) | [Architecture](pucklogic-architecture.md) §5.4 |
| Free tier | Default rankings (all players, preset weights) — read-only, no customization | Spec 009 review |
| Kit pass | Unlocks custom source weights, saved kits, export | Spec 009 review |
| Session token model | $2.99/session via Stripe, tokens purchased in advance | [Architecture](pucklogic-architecture.md) §7.5 |
| ESPN-first launch | ESPN required; Yahoo best-effort only | [Spec 008](specs/008-live-draft-sync-launch-required.md) §D5 |
| One active session per user | Yes at launch | [ADR 007](adrs/007-web-first-draft-session-and-temp-kit-lifecycle.md) |
| Suggestion rationale cohort | Top 50% of expected draft pool (default 108 of 216) | [Spec 009](specs/009-web-draft-kit-ux.md) |
| Archive at launch | No — rename, duplicate, delete only | [Spec 009](specs/009-web-draft-kit-ux.md) |
| Kit pass price | $4.99 one-time | Milestone B approval |
| Draft pass price | $2.99/session | [Architecture](pucklogic-architecture.md) §7.5 |
| Kit pass + draft pass pricing | Sold separately; no bundle at launch | Milestone B approval |
| Closed beta feedback pipeline | Discord + structured prompt; user sourcing deferred to Aug 2026 | Milestone B approval |

---

## Key Architecture References

| Doc | Purpose |
|---|---|
| [pucklogic-architecture.md](pucklogic-architecture.md) | Tech stack, DB schema, algorithms, hosting |
| [backend-reference.md](backend-reference.md) | API routes, SQL DDL, security model |
| [frontend-reference.md](frontend-reference.md) | App Router pages, Zustand stores, auth flow |
| [extension-reference.md](extension-reference.md) | Platform adapters, WebSocket protocol, monetization |
| [specs/INDEX.md](specs/INDEX.md) | All specs |
| [plans/INDEX.md](plans/INDEX.md) | All implementation plans |
| [adrs/INDEX.md](adrs/INDEX.md) | All architecture decision records |
| [research/INDEX.md](research/INDEX.md) | Research and brainstorm docs |

---

## External Tracking

| Tool | Purpose | Link |
|---|---|---|
| Notion Task Board | Sprint cards, feature tracking | [Task Board](https://www.notion.so/753d7997feb745c691997 2fdff385da3) |
| Notion Business Plan | Business context and strategy | [Business Plan](https://www.notion.so/322488853275812fa6d1fe73b8a80950) |
| Notion Product Roadmap | High-level product milestones | See Notion workspace |
| GitHub | Issues, PRs, CI | Active repo |

---

## Cut Rules

| If behind by | Cut |
|---|---|
| Mid-May | Non-essential UI complexity; narrow config surface |
| Late June | Simplify rankings UI; treat export as primary draft-day product |
| Late July | Make ML optional or lower-visibility |
| Late August | Defer extension; launch web draft kit only |
