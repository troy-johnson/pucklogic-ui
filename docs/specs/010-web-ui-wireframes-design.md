# 2026-04-09 — Web UI Wireframes Design

**Status:** Approved with nits — adversarial review round 1 complete (2026-05-06)  
**Milestone:** B → D — Locks wireframe decisions; feeds Milestone D implementation plan  
**Related:** `docs/specs/009-web-draft-kit-ux.md`, `docs/plans/008a-draft-season-readiness.md`

---

## Context

Spec 009 (approved 2026-04-09) defines the UX contract for the web draft kit. This doc captures the wireframe-level layout decisions made during Milestone B design review — the structural choices that shape implementation: app shell, navigation, workspace layouts, live draft session, and entry flow.

Design system (colors, typography, spacing tokens) is defined in the Design System section below. Token set locked 2026-05-06.

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

### Color palette (locked 2026-05-05 — from Claude Design session)

**UI accent: Emerald `#34d399`** — nav active state, pill-active, slider fill, Compute button gradient. Chosen over violet (too quiet for sports-data context) and rose (conflicts with error/down-trend red vocabulary). Passes AA contrast against `#111319` base and `#191b22` surface.

**Source identity colors (fixed — data role only, never used as UI chrome):**
- DF (Dobber Fantasy): `#a4c9ff` (blue)
- EP (Elite Prospects): `#45dfa4` (green) — distinct luminance from emerald accent
- NST (Natural Stat Trick): `#facc15` (yellow)

| Token | Dark | Light | Purpose |
|---|---|---|---|
| `--bg-base` | `#111319` | `#f8fafc` | Page background |
| `--bg-low` | `#191b22` | `#f1f5f9` | surface-container-low |
| `--bg-surface` | `#1e1f26` | `#ffffff` | Cards, panels |
| `--bg-raised` | `#282a30` | `#e8eef6` | Alternate rows, context bar |
| `--bg-highest` | `#33343b` | `#dde5f0` | Highest elevation surfaces |
| `--border` | `rgba(65,71,81,0.18)` | `rgba(148,163,184,0.25)` | Ghost dividers — no 1px solid lines |
| `--border-mid` | `rgba(65,71,81,0.35)` | `rgba(148,163,184,0.45)` | Slightly more visible ghost |
| `--text-primary` | `#e2e2eb` | `#1e293b` | Body text |
| `--text-secondary` | `#c1c7d3` | `#475569` | Labels, metadata |
| `--text-muted` | `#8b919d` | `#94a3b8` | Placeholders, de-emphasized |
| `--accent-blue` | `#34d399` | `#059669` | **UI accent (emerald)** — nav, pills, sliders, CTA |
| `--accent-green` | `#45dfa4` | `#059669` | EP source identity / sync status |
| `--accent-yellow` | `#facc15` | `#d97706` | NST source identity / suggestions / warnings |
| `--accent-red` | `#ffb4ab` | `#dc2626` | Errors, down-trend, urgent needs |

> Note: The `--accent-blue` CSS variable is repurposed as the primary UI accent (emerald). The variable name is kept for code compatibility — it does not imply blue in the final implementation.

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

The `/` route is a value prop marketing page — no auth required. Authenticated users hitting `/` are redirected to `/dashboard` by middleware.

Design reference: Claude Design landing.jsx variant C.

```
┌─────────────────────────────────────────────────┐
│  PuckLogic  Features Pricing Sources Docs        │
│                              [Sign in] [Start]   │
├─────────────────────────────────────────────────┤
│                                                  │
│        [hero headline + subhead]                 │
│        [primary CTA]                             │
│                                                  │
├─────────────────────────────────────────────────┤
│  01 League profile  02 Weight sources  03 Draft  │  ← steps strip
├─────────────────────────────────────────────────┤
│  [features grid — 3×2]                          │
├─────────────────────────────────────────────────┤
│  [pricing section]                              │
├─────────────────────────────────────────────────┤
│  footer                                         │
└─────────────────────────────────────────────────┘
```

- Sticky glassmorphism nav (logo, links, sign in + start CTA)
- No kit context bar — this is the public marketing surface
- **Post-launch:** add a "browse default rankings" section or `/rankings` route for unauthenticated exploration

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

shadcn/ui is the component library. All tokens are CSS custom properties in `globals.css`, referenced in `tailwind.config.ts`. shadcn/ui provides the accessible interaction layer; token overrides carry the visual identity.

### Typography

**Families**
- `--font-sans`: `'Inter', -apple-system, BlinkMacSystemFont, sans-serif` — feature settings `cv11`, `ss01`
- `--font-mono`: `'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, monospace` — tabular-nums

**Scale**

| Token | Size | Weight | Letter-spacing | Use |
|---|---|---|---|---|
| `display` | 42px | 800 | −1.5px | Landing hero only |
| `heading-lg` | 28px | 700 | −0.5px | Page section titles |
| `heading-md` | 20px | 800 | −0.5px | Card / modal headlines |
| `heading-sm` | 16px | 700 | −0.3px | Panel section headers |
| `body-lg` | 14px | 400 | — | Table rows, descriptions |
| `body` | 13.5px | 400/600 | — | General UI copy |
| `body-sm` | 13px | 400/500 | — | Labels, metadata |
| `caption` | 12px | 500 | — | Timestamps, hints |
| `overline` | 10–11px | 700 | +0.06–0.08em | Section labels (uppercase) |
| `mono` | 13–14px | 600–700 | — | Scores, ranks, pass counts |

Line-height: `1.5` for body; `1.15–1.2` for headings.

---

### Spacing

Base unit: `4px`. Scale: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64.

| Context | Value |
|---|---|
| Intra-component gap (icon + label) | 6–8px |
| Component internal padding | 10–14px vertical, 12–16px horizontal |
| Panel / section padding | 16–24px |
| Page section padding | 48–64px |
| Stack gap between form fields | 8–12px |

---

### Border radius

| Element | Radius |
|---|---|
| Button, input, small card | 4px |
| Drawer panel, medium card | 6px |
| Large card (landing) | 8px |
| Pill / badge / avatar | 99px (fully rounded) |
| Search input | 2px |
| Slider thumb | 99px |

---

### Elevation / shadows

| Layer | Shadow / treatment |
|---|---|
| Suggestion priority card | `0 10px 20px rgba(0,0,0,0.18)` |
| Drawer / slide-in panels | `−8px 0 40px rgba(0,0,0,0.45)` |
| Modal / empty-state card | `0 24px 60px rgba(0,0,0,0.32)` |
| Scrim (drawer backdrop) | `rgba(10,12,18,0.68)` + `backdrop-filter: blur(3px)` |
| Sticky table header | `backdrop-filter: blur(4px)` — no shadow |

Panel separation uses surface tier shifts (`--bg-base` → `--bg-highest`), not `box-shadow`.

---

### Component primitives

| Class | Description |
|---|---|
| `.pl-btn` | Base: flex, gap 6px, br 4px, 13px/500, no border |
| `.pl-btn-primary` | Gradient `#34d399→#10b981`, text `#052e1c`, 7px 14px padding |
| `.pl-btn-outline` | Transparent bg, `--border-mid` border, `--text-primary` |
| `.pl-btn-ghost` | Transparent bg/border, `--text-muted`, hover bg-raised |
| `.pl-btn-danger` | `--accent-red` text, ghost base — destructive actions only |
| `.pl-input` | bg-low, no border, 7px 10px, br 2px; focus: `box-shadow 0 0 0 1px --accent-blue` |
| `.pl-pill` | 5px 14px, br 99px, 11px/700 uppercase — position filter tabs |
| `.pl-pill-active` | bg-highest, `--accent-blue` text |
| `.pl-th` | 10px/700 uppercase, sticky, `backdrop-filter: blur(4px)` |
| `.pl-td` | 14px, `--text-primary`, `border-bottom: 1px solid --border` |
| `.pl-row` | hover `rgba(52,211,153,0.06)`, `transition: background 0.08s` |
| `.pl-slider-track` | 6px tall, bg-highest, br 99px |
| `.pl-slider-fill` | `--accent-blue`, absolute fill, `transition: width 0.06s` |
| Skeleton | shadcn/ui `<Skeleton>` with `animate-pulse`; bg-highest override |
| Toast | shadcn/ui `<Sonner>` with dark token override |
| Scrollbar | 6px wide, `--border-mid` thumb, transparent track |

---

### Icon set

**Lucide React** — shadcn/ui default. Icons rendered at 14–16px, stroke-width 1.5–2. `lucide-react` named imports in production; inline SVG used only in design prototypes.

---

### Motion

| Interaction | Duration | Easing |
|---|---|---|
| Drawer slide-in / slide-out | 260ms | `cubic-bezier(0.32, 0, 0.08, 1)` |
| Scrim fade | 220ms | `ease` |
| Button / row hover bg | 80–120ms | `ease` |
| Button state change (confirm) | 160ms | `ease` |
| Slider fill | 60ms | `ease` |
| Live pulse dot | 1600ms | `ease-in-out infinite` |
| Skeleton shimmer | shadcn default `animate-pulse` | — |

Rank reorder on table repopulation is instant — the sudden reorder communicates urgency intentionally.

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
| Landing page (launch) | Value prop marketing page (Claude Design variant C); auth users → `/dashboard` |
| Landing page (post-launch) | Add `/rankings` browsable default rankings for unauthenticated users |
| Pick log | Accessible via drawer, not persistent |
| Reconnect state | Banner (not modal), inline action |
| Route shape — live draft | `/live` with own layout under `(auth)` route group; not nested under `/dashboard` |
| Pass balance fetch | Server Component layout; `router.refresh()` post-purchase; no SWR/Zustand |
| Auth state | Server-fetched session + thin `<UserProvider>` client context; no Zustand auth slice |
| Token sequencing | Globals.css written in Wave 1 before any component work |
| Design system | Complete — see Design System section above |

---

## Adversarial Review Record

**Packet path:** inline (no external file)
**Round:** 1
**Date:** 2026-05-06
**Verdict:** `APPROVED WITH NITS`

### Findings

**F-1 (Important) — Layout caching caveat for entitlements**
Next.js App Router preserves shared layouts on client-side navigation — the Server Component does not re-render between `/dashboard` and `/live`. Entitlements are fetched only on hard navigation or explicit `router.refresh()`. This is correct behavior for pass balance (only changes post-purchase), but must be explicitly wired: post-purchase redirect pages must call `router.refresh()`. Carried forward to plan 010a Wave 2.

**F-2 (Important) — shadcn/ui token bridge required**
shadcn/ui reads its own CSS custom property namespace (`--primary`, `--background`, `--foreground`, etc. as HSL values). PL tokens use a parallel namespace (`--accent-blue`, `--bg-base`, etc.). Without an explicit bridge in `globals.css`, shadcn components render with their own defaults. Plan 010a Wave 1 must map PL values to shadcn token names. Carried forward as a Wave 1 task.

**F-3 (Minor) — No formal acceptance criteria in this spec**
Spec is design-document style; AC will be defined per-component in plan 010a.

### Pre-plan gate
Met. Adversarial verdict is `APPROVED WITH NITS`. Planning may proceed.
