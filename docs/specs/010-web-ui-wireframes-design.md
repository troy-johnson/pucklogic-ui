# 2026-04-09 — Web UI Wireframes Design

**Status:** Draft — design system section pending  
**Milestone:** B → D — Locks wireframe decisions; feeds Milestone D implementation plan  
**Related:** `docs/specs/009-web-draft-kit-ux.md`, `docs/plans/008a-draft-season-readiness.md`

---

## Context

Spec 009 (approved 2026-04-09) defines the UX contract for the web draft kit. This doc captures the wireframe-level layout decisions made during Milestone B design review — the structural choices that shape implementation: app shell, navigation, workspace layouts, live draft session, and entry flow.

Design system (colors, typography, spacing tokens) is a follow-on section to be completed before Milestone D begins.

---

## App Shell

### Layout

**Slim header + kit context bar (Option C from exploration)**

```
┌─────────────────────────────────────────────────┐
│  PuckLogic                     [user]  [3 passes]│  ← persistent header
├─────────────────────────────────────────────────┤
│  Kit: ESPN H2H 10-team ▾  League ▾  Weights ▾  ▶ Compute │  ← kit context bar
├─────────────────────────────────────────────────┤
│                                                  │
│   [page content]                                 │
│                                                  │
└─────────────────────────────────────────────────┘
```

- **Header:** logo, user avatar/menu, draft pass balance (always visible)
- **Kit context bar:** active kit name (clickable — opens kit switcher), league profile dropdown, source weights dropdown, compute action
- **No persistent sidebar** — table gets maximum horizontal space
- Navigation between major sections (kit library, live session) happens via the context bar and kit switcher panel

### Mobile behavior

- Kit context bar controls collapse into a single menu icon
- Right panels (weights, kit switcher) become full-screen drawers
- Rankings table goes full width

---

## Color Theme

- **Default:** system preference (OS dark/light)
- **User override:** dark or light, selectable in account settings
- **Post-launch:** A/B test whether dark or light default improves conversion; switch default if one clearly wins

### Color palette (placeholder — to be defined in design system section)

| Token | Dark | Light | Purpose |
|---|---|---|---|
| `--bg-base` | `#0f1117` | `#f8fafc` | Page background |
| `--bg-surface` | `#1a1d27` | `#ffffff` | Cards, panels |
| `--bg-raised` | `#1e2130` | `#f1f5f9` | Alternate rows, context bar |
| `--border` | `#2d3148` | `#e2e8f0` | Dividers |
| `--text-primary` | `#e2e8f0` | `#1e293b` | Body text |
| `--text-secondary` | `#94a3b8` | `#64748b` | Labels, metadata |
| `--text-muted` | `#475569` | `#94a3b8` | Placeholders |
| `--accent-blue` | `#60a5fa` | `#2563eb` | Links, actions |
| `--accent-green` | `#34d399` | `#059669` | Sync status, success |
| `--accent-yellow` | `#fbbf24` | `#d97706` | Suggestions, warnings |
| `--accent-red` | `#f87171` | `#dc2626` | Urgent needs, errors |

---

## Entry Flow

### Authenticated users

1. Auto-load last-used kit directly into the pre-draft workspace
2. First-time users (no kits yet): show an empty state with "Create your first kit" CTA
3. Other kits and "New kit" always accessible via the kit switcher (see below)

### Unauthenticated users

- Land on default rankings view (see Landing Page section)
- Auth gate appears inline when they attempt to save, export, or start a live session

---

## Kit Switcher

Triggered by clicking the kit name in the context bar. Opens a **slide-in panel from the right** over the workspace.

```
┌─────────────────────────────────────┐
│ Your kits                      [✕]  │
│─────────────────────────────────────│
│ ┌─────────────────────────────────┐ │
│ │ ✓ ESPN H2H 10-team              │ │  ← active kit
│ │   Last used: today              │ │
│ └─────────────────────────────────┘ │
│ ┌─────────────────────────────────┐ │
│ │   Yahoo Roto 12-team            │ │
│ │   Last used: 3 days ago         │ │
│ └─────────────────────────────────┘ │
│ ┌─────────────────────────────────┐ │
│ │   Keeper League 2026            │ │
│ │   Last used: 1 week ago         │ │
│ └─────────────────────────────────┘ │
│                                     │
│  + New kit                          │
└─────────────────────────────────────┘
```

- Selecting a kit closes the panel and reloads the workspace with that kit
- Each kit card has a `···` overflow menu: rename, duplicate, delete
- "New kit" opens kit creation flow (name → league profile → weights → compute)
- On mobile: panel is full-screen

---

## Pre-Draft Workspace

**High fidelity target**

### Layout

**Persistent right panel (Option B from exploration)**

```
┌─────────────────────────────────────────────────────────────┐
│  Kit context bar                                             │
├──────────────────────────────────┬──────────────────────────┤
│                                  │  League profile           │
│  Rankings table                  │  ESPN H2H, 10-team        │
│                                  │  ─────────────────────    │
│  #  Player        Pos  Score     │  Source weights           │
│  1  McDavid       C    98.4  ↑   │  DF  ████░░  65          │
│  2  MacKinnon     C    96.1  —   │  EP  ███░░░  50          │
│  3  Kucherov      RW   94.8  ↓   │  NST █████░  80          │
│  4  Draisaitl     C    93.2  —   │  ─────────────────────    │
│  5  Makar         D    91.5  ↑   │  [Equalize]  [Reset]      │
│  ...                             │  ─────────────────────    │
│                                  │  [Export rankings]        │
│                                  │  [Export draft sheet]     │
└──────────────────────────────────┴──────────────────────────┘
```

- Right panel is persistent and always visible on desktop
- Rankings table includes per-source rank columns (DF, EP, NST, etc.) sortable by header
- Position filter tabs above table (All / C / LW / RW / D / G)
- Player row click opens player detail drawer (name, stats, source breakdown)
- "Working in temporary session — kit pass required to save" label shown for unauthenticated users with active temp kit
- On mobile: right panel collapses to a drawer triggered from context bar

### Rankings refresh signal

When rankings recompute after a weight change:
1. Table enters skeleton state (rows shimmer)
2. Table repopulates with new order
3. "Updated just now" timestamp appears in context bar; toast shown only on explicit compute action (suppressed on page load)

---

## Live Draft Session

**High fidelity target**

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│  ● Live  Round 3 · Pick 26   Your turn in 2   + Manual pick  │
├──────────────────────────────────┬──────────────────────────┤
│                                  │  SUGGESTED PICKS          │
│  Available players               │  ┌──────────────────────┐│
│                                  │  │ ① PRIORITY  need 2C  ││
│  #  Player      Pos  Score  Trend│  │ Draisaitl   C  93.2  ││  ← prominent
│  1  McDavid     C    98.4   ↑    │  └──────────────────────┘│
│  2  Draisaitl   C    93.2   —    │  ② if C gone   need 3D   │
│  3  Makar       D    91.5   ↑    │  Makar         D  91.5   │  ← quieter
│  4  Kucherov    RW   90.8   ↓    │                           │
│  5  Hellebuyck  G    88.2   —    │  ③ sleeper      need 1G  │
│  ...                             │  Hellebuyck    G  88.2   │  ← quietest
│                                  │  ─────────────────────── │
│                                  │  ROSTER NEEDS             │
│                                  │  C  1/3  need 2  🟡       │
│                                  │  LW 2/2  ✓       🟢       │
│                                  │  RW 1/2  need 1  🟡       │
│                                  │  D  1/4  need 3  🔴       │
│                                  │  G  0/2  need 2  🔴       │
│                                  │  ─────────────────────── │
│                                  │  MY TEAM (5 picks)        │
│                                  │  Ovechkin   LW   R1       │
│                                  │  Hedman     D    R2       │
│                                  │  Pastrnak   RW   R3       │
│                                  │  Barkov     C    R4       │
│                                  │  Gaudreau   LW   R5       │
│                                  │  ─────────────────────── │
│                                  │  ● Synced                 │
└──────────────────────────────────┴──────────────────────────┘
```

### Right panel — top to bottom

1. **Suggested picks** — priority-ordered by (positional need urgency × best available score at position)
   - ① Priority: prominent card with border highlight
   - ② If gone: muted, same structure
   - ③ Sleeper: quietest — for elite players at lower-need positions
2. **Roster needs grid** — filled/needed per position, color-coded (green=done, yellow=moderate need, red=urgent)
3. **My team** — picks in order with position and round
4. **Sync status bar** — `● Synced` / `↻ Reconnecting` / `⚠ Manual mode` + manual pick entry link

### Pick log

Accessible via a drawer (not always visible). Shows all picks in draft order with your picks highlighted.

### Sync status states

| State | Indicator | Action available |
|---|---|---|
| Connected | `● Synced` (green) | — |
| Reconnecting | `↻ Reconnecting…` (yellow, pulse) | Wait or switch to manual |
| Disconnected | `⚠ Disconnected` (red) | Reconnect / switch to manual |
| Manual mode | `✎ Manual mode` (blue) | Enter picks manually |

---

## Landing Page (Unauthenticated `/`)

The `/` route shows default PuckLogic rankings — no auth required.

```
┌─────────────────────────────────────────────────┐
│  PuckLogic                    [Sign in] [Sign up]│
├─────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────┐  │
│  │  Default rankings — ESPN H2H baseline     │  │  ← info banner
│  │  Sign in to customize and save your kit   │  │
│  └───────────────────────────────────────────┘  │
│                                                  │
│  [All positions ▾]  [Filter...]                  │
│                                                  │
│  #  Player        Pos  Score                     │
│  1  McDavid       C    98.4                      │
│  2  MacKinnon     C    96.1                      │
│  ...                                             │
└─────────────────────────────────────────────────┘
```

- No kit context bar (no active kit)
- No source weight panel (defaults only)
- Info banner explains what they're seeing and CTAs to sign in/up
- **Post-launch:** replace with a proper marketing landing page (hero + login CTA + minified rankings hook)

---

## Supporting Screens (Medium Fidelity)

### Auth gate
Inline drawer or modal — appears when unauthenticated user attempts to save, export, or start a live session.

- **Save kit:** "Sign in to save your kit" + sign in / create account CTAs
- **Export:** "Kit pass required to export" + purchase CTA (if authed but no kit pass)
- **Live draft:** "Draft pass required" + purchase CTA + sign in if not authed

### Start live draft session modal
- Draft pass confirmation ("1 pass will be used")
- ESPN connection prompt with extension install link (Milestone I)
- "Start without sync (manual mode)" fallback option

### Manual pick entry
Slide-in drawer. Player search field → select player → confirm. Writes to session state same as auto-detected picks.

### Reconnect state
**Not a modal** — a banner at the top of the live draft session screen:

```
┌──────────────────────────────────────────────────────┐
│  ↻ Reconnecting to draft session…  [Switch to manual] │
└──────────────────────────────────────────────────────┘
```

Resolves automatically when reconnected; banner dismisses. If reconnect fails after timeout, offer manual mode or session end.

### Kit library
Accessible via the kit switcher slide-in panel (not a separate page). Kit cards show: name, league type, last used date, overflow menu (rename, duplicate, delete).

---

## Design System

> **Pending — to be defined before Milestone D begins.**

Sections to complete:

- **Typography:** font family, scale (heading sizes, body, label, mono), line-height
- **Spacing:** base unit, scale, padding/gap conventions
- **Color tokens:** full dark + light palette (see placeholder table in Color Theme section)
- **Border radius:** card, button, input, badge conventions
- **Shadows / elevation:** surface layering for panels, modals, drawers
- **Component primitives:** button variants (primary, secondary, ghost, danger), input, select, slider, badge, toast, skeleton
- **Icon set:** which library (e.g. Lucide, which is default with shadcn/ui)
- **Motion:** transition timing for drawers, toasts, skeleton → content

shadcn/ui is the component library (already in stack). Tokens should be defined as CSS custom properties in `globals.css` and referenced in Tailwind config.

---

## Decisions Log

| Decision | Resolution |
|---|---|
| App shell layout | Slim header + kit context bar (no sidebar) |
| Mobile nav | Context bar collapses to menu icon; panels become full-screen drawers |
| Color theme | System default; user-overridable; A/B default post-launch |
| Entry flow (authed) | Auto-load last kit; kit switcher for others |
| Kit switcher | Slide-in panel with metadata + overflow actions |
| Pre-draft workspace | Persistent right panel (weights + league + export) |
| Live draft layout | Full-width available players + right panel (suggestions → needs → team) |
| Suggestion panel | Priority-ordered by need × value; 3 picks shown (①②③) |
| Roster needs | Grid per position, color-coded urgency |
| Landing page (launch) | Default rankings view with info banner |
| Landing page (post-launch) | Marketing page with hero + CTA + minified rankings |
| Pick log | Accessible via drawer, not persistent |
| Reconnect state | Banner (not modal), inline action |
| Design system | Pending — before Milestone D |
