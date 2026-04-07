# PuckLogic Roadmap

**Launch target:** Mid-September 2026  
**Strategy:** Ship web draft kit first. Extension is conditional — proceeds only if it does not jeopardize the web launch.  
**Current date:** 2026-04-07  
**Solo dev — nights and weekends**

---

## Milestone Status

| Milestone | Window | Status | Key Docs |
|---|---|---|---|
| A — Scraper hardening + backfill | Mar 28 – Apr 12 | In progress | [Plan 008a](plans/008a-draft-season-readiness.md) |
| F — First real ML execution | Apr 13 – Apr 20 | Upcoming | [Plan 008a §F](plans/008a-draft-season-readiness.md#milestone-f--first-real-ml-execution-run) |
| B — Lock draft kit workflow / UI scope | Apr 21 – May 4 | Upcoming | [Spec 009](specs/009-web-draft-kit-ux.md) · [ADR 007](adrs/007-web-first-draft-session-and-temp-kit-lifecycle.md) |
| C — Backend integration verification | May 5 – May 18 | Planned | [Plan 008a §C](plans/008a-draft-season-readiness.md#milestone-c--verify--gap-fill-backend-integration) |
| D — Build web draft kit UI | May 19 – Jun 29 | Planned | [Spec 009](specs/009-web-draft-kit-ux.md) |
| E — Polish exports | Jun 30 – Jul 13 | Planned | [Plan 008a §E](plans/008a-draft-season-readiness.md#milestone-e--make-exports-launch-grade) |
| G — Launch hardening | Jul 14 – Aug 17 | Planned | [Plan 008a §G](plans/008a-draft-season-readiness.md#milestone-g--harden-the-web-launch) |
| H — Extension go/no-go | Aug 18 – Aug 24 | Conditional | [Plan 008a §H](plans/008a-draft-season-readiness.md#milestone-h--extension-gono-go) |
| I — Extension MVP / beta | Aug 25 – Sep 14 | Conditional | [Spec 008](specs/008-live-draft-sync-launch-required.md) · [Plan 008a §I](plans/008a-draft-season-readiness.md#milestone-i--extension-mvp--beta-conditional) |

---

## Open Architecture Work

Items identified during Milestone B spec review that need to land in later milestones.

### Milestone B approval (Apr 21 – May 4)
- [ ] Approve payment model: default rankings free · kit customization = kit pass · live draft = session tokens
- [ ] Approve token-based session model (buy tokens in advance, consume at draft room entry)
- [ ] Approve closed beta strategy and feedback pipeline

### Milestone C backend additions (May 5 – May 18)
- [ ] Design and implement `draft_tokens` table (purchased but unconsumed sessions — current `subscriptions` schema does not support this)
- [ ] Update Stripe checkout flow: purchase creates tokens, not a direct session
- [ ] Token balance readable by both web app and extension
- [ ] Kit pass entitlement gating for customization and export paths
- [ ] Snapshot PuckLogic rankings into session record at session close — required for post-season "ranking vs. actual performance" ML comparison job (no UI needed; backend only)

### Milestone I extension additions (Aug 25 – Sep 14)
- [ ] Draft room detection → token consumption prompt ("Use PuckLogic for this draft? X sessions remaining")
- [ ] Token balance visible in extension popup
- [ ] Manual session start from extension with explicit token consumption
- [ ] Auto-revert from manual fallback when sync recovers (extension-side, with user notification)

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
