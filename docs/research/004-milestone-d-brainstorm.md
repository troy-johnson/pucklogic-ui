# Brainstorm: Milestone D — Web Draft Kit UI

**Date:** 2026-05-06  
**Track:** research → brainstorm  
**Feeds:** spec 010 (design system completion) → plan 010a (revised wave order)  
**Resolves:** 5 open questions from `docs/research/003-milestone-d-web-ui-codebase-survey.md`

---

## Decisions

### 1. Route shape for live draft screen

**Decision: `/live` — separate route with own layout under the `(auth)` route group**

```
src/app/(auth)/
  layout.tsx          ← auth boundary (session check + redirect)
  dashboard/
    page.tsx          ← pre-draft workspace
    layout.tsx        ← kit context bar chrome
  live/
    page.tsx          ← live draft screen
    layout.tsx        ← live-mode chrome (no kit bar, reconnect banner strip)
```

Rejected: `/dashboard/live` (requires layout branching conditionals based on path). Rejected: `/draft/*` reorganisation (breaking rename of existing `/dashboard` route, not worth it now).

**Rationale:** The live draft screen has categorically different chrome — no kit context bar, adds reconnect banner, different action area. Giving it its own `layout.tsx` keeps each layout file focused on one thing. Auth protection is inherited from the `(auth)` route group middleware — no duplication.

---

### 2. Pass balance in the shell header

**Decision: Fetch in the Server Component layout — no SWR, no Zustand**

`(auth)/layout.tsx` is a Server Component. It reads the Supabase session from cookies and fetches `/api/entitlements` (or direct DB read) server-side. Pass balance is passed as a prop to the shell header.

Post-purchase refresh: Stripe redirect page calls `router.refresh()` → layout re-renders server-side → balance updates. No manual cache invalidation.

Rejected: SWR hook in shell (client-side waterfall for server-readable data). Rejected: Zustand entitlements slice (duplicates server-authoritative data on the client, requires manual invalidation).

**Rationale:** Established pattern for this codebase — prefer Server Components where possible. Auth session and entitlements are readable from cookies on every server request; there is no reason to re-fetch them client-side.

---

### 3. Landing page shape

**Decision: Distinct `/` — value prop landing page (Claude Design variant C); authenticated users redirect to `/dashboard`**

```
/               ← Server Component, public, value prop landing page
/dashboard      ← auth required, pre-draft workspace
/live           ← auth required, live draft screen
```

Middleware: authenticated users at `/` redirect to `/dashboard`. The landing page uses the Claude Design landing.jsx variant C (nav, steps strip, features grid, pricing, CTA).

The "view default rankings" browsing experience from the empty-state wireframe can be added as `/rankings` post-launch — not a Wave 1 blocker.

Rejected: `/` as rankings table with CTA banner (landing page design already exists and is the better first impression). Rejected: `/` redirects all users to `/dashboard` (odd URL for unauthenticated users, loses SEO value).

---

### 4. Auth state pattern

**Decision: Server-fetched session + thin `<UserProvider>` client context**

`(auth)/layout.tsx` fetches the user server-side and passes it as initial state into a lightweight `<UserProvider>` Client Component. Client components anywhere in the tree can call `useUser()`. The Supabase browser client subscribes to `onAuthStateChange` inside the provider to handle mid-session expiry.

```
(auth)/layout.tsx  (Server Component)
  → createClient() [server]
  → const user = await getUser()
  → <UserProvider initialUser={user}>   ← 'use client' boundary here only
      {children}
    </UserProvider>
```

The `auth` Zustand slice from the reference doc is dropped. Auth is not Zustand's job.

Rejected: Pure SSR-only (prop drilling auth state into all client components is impractical at scale). Rejected: Zustand auth slice (client-side duplication of server-authoritative state).

**Rationale:** Supabase's own App Router guide recommends this exact pattern. Server Components get the authoritative path; Client Components get a clean `useUser()` without prop drilling.

---

### 5. Design system sequencing

**Decision: Tokens first — CSS custom properties before any component work (Wave 1)**

Write the full token set into `globals.css` before any component files are created. Every component references tokens from day one. Dark/light theme switching works immediately.

Revised wave order for plan 010a:

| Wave | Scope |
|---|---|
| 1 | Design system baseline: `globals.css` tokens, font setup, Tailwind config extension |
| 2 | Shell + landing: `AppShell`, `UserProvider`, auth middleware, `/` landing page, `/dashboard` redirect |
| 3 | Pre-draft workspace: `KitSwitcher`, `kits` store slice, `PreDraftWorkspace`, auth pages |
| 4 | Session API + state: `draftSession` store slice, `draft-sessions.ts` API client, `entitlements.ts` API client |
| 5 | Live draft screen: `LiveDraftScreen`, ESPN sync, manual pick drawer, reconnect banner |

Rejected: Tokens as Wave 5 retrofit (error-prone, dark mode broken throughout dev, two passes on every component).

---

## Cross-cutting principle established

**Prefer Server Components.** Data that is readable server-side (session, entitlements, rankings) is fetched in Server Component layouts/pages and passed as props. Zustand is reserved for client-only interactive state: active kit selection (unsaved edits), draft session pick log (live interactive), UI toggle state (drawer open/closed).

---

## Resolved questions (not ADRs)

All 5 open questions from research doc 003 are now resolved. No architectural decisions flagged for ADR at this stage — the choices are implementation-level and scoped to Milestone D.

---

## Open questions carried forward to spec

None. Brainstorm is complete. Spec 010 design system section is the only remaining gap before plan 010a is written.

---

## Next step

Update spec 010 design system section (typography, spacing, radius, elevation, component primitives, icon set, motion) → then write revised plan 010a.
