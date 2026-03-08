# PuckLogic Draft Kit
## Technical Architecture & Roadmap

**Version 1.0 · March 2026 · Confidential**

## Scope of This Document

This document covers the full technical architecture, technology decisions, and phased delivery roadmap for the PuckLogic Draft Kit — including the aggregation dashboard, browser extension draft monitor, PDF/Excel exports, and the Trends prediction engine.

**Target launch:** before the 2026–27 NHL season (September 2026).

---

## 1. Executive Summary

PuckLogic's Draft Kit is a two-product suite targeting casual and competitive/keeper fantasy hockey players. The first product is a free-to-use rankings aggregator — users select sources, assign weights, and receive a custom consensus ranking. The second is a paid real-time draft monitor delivered as a browser extension that tracks picks live and surfaces AI-powered draft suggestions.

A secondary feature — the **Trends engine** — layers predictive analytics on top of the rankings, surfacing breakout candidates and regression risks using a custom ML model trained on historical NHL data.

---

## 2. Product Architecture Overview

PuckLogic is structured as three loosely-coupled layers: a data ingestion and processing pipeline, a backend API, and a frontend suite (web app + browser extension). The diagram below maps how these interact.

### System Diagram (Logical)

```
┌─────────────────────────────────────────────────────────┐
│                  DATA SOURCES                           │
│  Dobber · Dom Luszczyszyn · NST/MoneyPuck               │
│  NHL.com API · Elite Prospects · User CSVs              │
└──────────────────────┬──────────────────────────────────┘
                       │  Scrapers + Parsers (Python)
┌──────────────────────▼──────────────────────────────────┐
│              INGESTION PIPELINE                         │
│  GitHub Actions cron · Normalized player DB             │
│  Supabase PostgreSQL · Redis cache (Upstash)            │
└──────────────────────┬──────────────────────────────────┘
                       │  REST + WebSocket
┌──────────────────────▼──────────────────────────────────┐
│              FASTAPI BACKEND                             │
│  Rankings aggregation  ·  Trends ML inference           │
│  Export generation     ·  Auth (Supabase JWT)           │
│  Stripe webhooks       ·  Draft session state           │
└────────┬──────────────────────────────┬─────────────────┘
         │  HTTPS / REST                 │  WebSocket
┌────────▼───────────┐     ┌─────────────▼───────────────┐
│  NEXT.JS WEB APP   │     │  CHROME EXTENSION (MV3)      │
│  Free dashboard    │     │  Paid — $2–3 / draft session │
│  Export checkout   │     │  ESPN Fantasy overlay        │
└────────────────────┘     └─────────────────────────────┘
```

### Technology Decisions at a Glance

| Dimension | Decision |
|-----------|----------|
| Primary users | Casual redraft + competitive keeper players |
| Monetization | Freemium → extension upsell → one-time exports |
| Frontend | Next.js (see Section 3) |
| Backend | FastAPI (Python) on Railway / Fly.io |
| Database | Supabase (PostgreSQL + Auth + Storage) |
| ML / Trends | Custom scikit-learn / XGBoost model, served via FastAPI |
| Draft monitor | Chrome extension (MV3) with ESPN Fantasy integration |
| Target launch | September 2026 |

---

## 3. Frontend: Next.js vs SvelteKit

Both are excellent choices. The recommendation is **Next.js** for PuckLogic's specific needs. Here is why:

The decisive factor is the browser extension. The Chrome extension will share UI components (player cards, ranking tables, suggestion panels) with the web app. React components can be used inside a MV3 extension directly; Svelte requires a separate compilation pipeline. A shared component library saves significant time across the dashboard and the extension's overlay UI.

### Next.js vs SvelteKit Comparison

| Factor | Next.js | SvelteKit | Winner |
|--------|---------|-----------|--------|
| Ecosystem maturity | Massive — Vercel backed, 5+ years | Growing fast, 3+ years stable | Next.js |
| Hiring / community | Largest React talent pool | Smaller but passionate | Next.js |
| Auth integrations | NextAuth, Supabase, Clerk all native | Good but less plug-and-play | Next.js |
| Stripe / payments | Mature examples, many tutorials | Possible, fewer examples | Next.js |
| Bundle size / perf | Heavier — but fine at this scale | Lighter, faster cold starts | SvelteKit |
| Learning curve | Medium (React familiarity assumed) | Lower for new devs | SvelteKit |
| Extension compatibility | React shared component library | Separate build needed | Next.js |
| Long-term support | Near-certain (Vercel revenue) | Community dependent | Next.js |

### Next.js Setup Recommendation

- **Framework:** Next.js 14+ with App Router
- **Styling:** Tailwind CSS + shadcn/ui component library
- **State:** Zustand (lightweight, no boilerplate)
- **Data fetching:** SWR or React Query for client-side, Server Components for SSR
- **Auth:** Supabase Auth (JWT, social login, magic link)
- **Hosting:** Vercel free tier → Pro as needed (free tier is generous)
- **Monorepo:** Turborepo with packages/ui for shared components

---

## 4. Backend Architecture

### 4.1 Framework: FastAPI (Python)

FastAPI is the right choice here because the ML/Trends model will be written in Python (scikit-learn / XGBoost). Keeping the backend in the same language eliminates a serialization boundary — model inference runs in the same process as the API, with no inter-service latency for predictions.

**Stack:**

- **FastAPI:** async Python REST + WebSocket API
- **Supabase:** PostgreSQL (player data, users, sessions), Auth, file Storage (exports)
- **Upstash Redis:** caching aggregated rankings (TTL-based, avoids repeat scrapes)
- **Celery + Redis:** background task queue for export generation and scrape jobs
- **Railway or Fly.io:** deployment — both have generous free tiers and cheap scaling

### 4.2 Database Schema (Core Entities)

The core PostgreSQL schema revolves around players, sources, and user draft sessions.

**Key Tables:**

| Table | Purpose |
|-------|---------|
| `players` | NHL player master (id, name, team, position, dob, nhl_id) |
| `player_rankings` | per-source rankings (player_id, source, rank, score, season, scraped_at) |
| `player_stats` | raw stats per season (goals, assists, TOI, CF%, xGF%, etc.) |
| `player_trends` | ML output (breakout_score, regression_risk, confidence, updated_at) |
| `sources` | registered aggregation sources (name, url, scrape_config, active) |
| `user_kits` | saved user weighting configs (user_id, weights JSON, name) |
| `draft_sessions` | live draft state (user_id, league_config, picks[], available[]) |
| `exports` | export job records (user_id, type, status, storage_url) |
| `subscriptions` | Stripe subscription state (user_id, plan, expires_at) |

### 4.3 Rankings Aggregation API

The aggregation algorithm is intentionally simple and transparent — users can see and understand how their custom rankings are computed. This builds trust and is a key UX differentiator.

**Algorithm:**

1. Each source assigns a rank (1 = best). Ranks are normalized to a 0–1 score.
2. User-defined weights (summing to 1.0) are applied to each source score.
3. Weighted average produces a composite score. Players are sorted descending.
4. Missing source data degrades gracefully — weight redistributed to present sources.
5. Results cached in Redis for 6 hours. Manual refresh available (rate-limited per user).

### 4.4 Data Ingestion Pipeline

Each source requires a dedicated scraper. These run on a cron schedule via GitHub Actions (free tier covers this comfortably) and write normalized data to Supabase.

**Data Sources & Methods:**

| Source | Method | Frequency | Notes |
|--------|--------|-----------|-------|
| NHL.com stats | Official API (free, documented) | Daily | Most reliable source |
| Natural Stat Trick | HTML scraper (BeautifulSoup) | Daily | Respect robots.txt; rate limit |
| MoneyPuck | CSV downloads available | Daily | Easy — they publish CSVs |
| Dobber Hockey | HTML scraper | Weekly pre-season | May need Playwright for JS-rendered content |
| Dom Luszczyszyn | HTML scraper (The Athletic) | Weekly pre-season | Paywalled — user may need to paste content |
| Elite Prospects | HTML scraper + EP API (freemium) | Weekly | EP API preferred if budget allows |

#### Note on Paywalled Sources

The Athletic (Dom Luszczyszyn) is behind a paywall. Two options:

1. Allow users to paste ranking tables manually (CSV/text paste UI) — easiest legally.
2. Partner with The Athletic for a data agreement — ideal long-term.

**Launch with option 1; pursue option 2 in 2027.**

---

## 5. ML Model: The Trends Engine

### 5.1 What Projects Like MoneyPuck/NST Have Done

MoneyPuck uses expected goals (xG) models trained on shot quality data. Natural Stat Trick surfaces raw and score-adjusted Corsi/Fenwick/xG. Dom Luszczyszyn at The Athletic built a GARR (Goals Above Replacement Rate) model. These are all strong prior art, but none provide the specific forward-looking output PuckLogic needs: a per-player breakout probability and regression risk score, specifically for fantasy scoring contexts.

### 5.2 Recommended Model Architecture

Start with a gradient boosted tree model (XGBoost or LightGBM). These are interpretable, fast to train on tabular data, don't require GPUs, and perform extremely well on structured player data. Reserve neural approaches for a v2 after you have sufficient labeled outcomes.

### 5.3 Training Data

The model needs at least 10 seasons of historical NHL data to learn aging curves and breakout patterns reliably. Several free/cheap sources exist:

- **Hockey Reference** — season-level stats, free scraping
- **MoneyPuck** — publishes full historical CSV datasets for free
- **Natural Stat Trick** — historical game logs available
- **NHL Edge API** — official, increasingly detailed tracking data

**Label Construction:**

- A **'breakout'** is defined as a player scoring 20%+ more fantasy points than their trailing 2-season average in the following season.
- A **'regression risk'** is the inverse.
- Train on seasons 2008–2022, validate on 2023–2025.

### 5.4 Model Serving

The trained model is serialized with joblib and loaded into memory at FastAPI startup. Inference is synchronous and fast (<10ms per player). Batch re-scoring of all players runs nightly as a Celery task and writes results to the player_trends table. No separate ML serving infrastructure is needed at this scale.

#### Feature Groups for the Model

- **PRODUCTION HISTORY:** Goals, assists, points, PPP per 60 — last 3 seasons
- **USAGE / DEPLOYMENT:** TOI/game, PP time, zone starts, line position
- **EFFICIENCY METRICS:** xGF%, CF%, HDCF%, On-ice SH% vs career SH%
- **AGING CURVES:** Age, years in league, historical comps at same age
- **INJURY HISTORY:** Games missed per season, injury type, recency
- **LINEMATE QUALITY:** Teammates' average xGF%, line combination history
- **CONTRACT CONTEXT:** Contract year (motivation proxy), entry-level vs vet
- **SITUATION CHANGES:** Team trade activity, coach change, power play role shift

#### Tech Stack for ML

- **Training:** Python, pandas, scikit-learn, XGBoost / LightGBM
- **Validation:** SHAP for feature importance (builds user trust / explainability)
- **Tracking:** MLflow (local) → MLflow on Fly.io for experiment tracking
- **Serving:** joblib model loaded in FastAPI process
- **Retraining:** Yearly (pre-season), triggered manually or via GitHub Action

---

## 6. Browser Extension: Draft Monitor

### 6.1 Architecture

The draft monitor is a Chrome MV3 extension that injects a sidebar overlay onto the ESPN Fantasy draft room. It tracks picks in real time and surfaces ranked suggestions for who to draft next, based on the user's custom PuckLogic rankings.

### 6.2 ESPN Pick Detection

ESPN Fantasy's draft room renders picks into the DOM with predictable class names and structure. The content script uses a MutationObserver to watch for new pick elements. When a pick is detected, the player name and pick number are extracted and sent to the background service worker, which relays them to the PuckLogic backend via WebSocket. The backend updates the draft session state and returns the next best available player recommendations.

### 6.3 Real-Time Suggestion Engine

When the user is on the clock, the extension requests the top N available players from the backend ranked by the user's weighted kit, filtered by positional need. The backend uses a simple positional need algorithm: compare current roster slots to league settings, weight suggestions toward positions with open starter slots. This does not require ML — it's deterministic roster logic.

### 6.4 Monetization Flow

The extension is free to install but requires authentication. Draft session activation costs $2–3 (one-time per draft). Payment is handled via Stripe Checkout — the user pays on the PuckLogic web app, which writes an active session token to Supabase. The extension polls for this token at startup. No payment UI lives in the extension itself, which simplifies Chrome Web Store compliance.

#### Extension Component Map

- `manifest.json` — MV3 manifest, host permissions for espncdn.com
- `content_script.js` — Injected into ESPN draft room, observes DOM for picks
- `sidebar.jsx` — React component (built separately, injected as shadow DOM)
- `background.js` — Service worker, manages WebSocket to PuckLogic backend
- `popup.jsx` — Extension popup (login, kit selection, session start)
- `shared/components` — Imported from main Next.js monorepo (Turborepo package)

#### Risk: ESPN DOM Changes

**Risk:** ESPN can update their draft room UI at any time, breaking DOM selectors.

**Mitigation:**
- Use multiple selector fallbacks.
- Monitor for DOM structure in pre-season.
- Maintain a test fixture of the ESPN draft room HTML for regression testing.
- Have a manual fallback mode (user manually marks picks) for launch reliability.

---

## 7. Export Generation: PDF & Excel

### 7.1 PDF Cheat Sheet

The PDF export is a printable draft cheat sheet — the user's custom rankings, formatted for print with tier separations, positional filters, and Trends indicators. Generated server-side using WeasyPrint (Python) from an HTML template. Stored in Supabase Storage, returned as a download link. Generation takes 2–5 seconds — handled async via Celery.

### 7.2 Excel Workbook

The Excel export uses openpyxl (Python) to generate a multi-tab workbook: a master rankings sheet, a by-position sheet, and a Trends tab with breakout/regression scores. Conditional formatting highlights tiers and risk levels. Same async Celery job as PDF.

#### Export Options

| Export Type | Library | Price Point | Delivery |
|-------------|---------|-------------|----------|
| PDF cheat sheet | WeasyPrint (Python) | $1–2 one-time | Supabase Storage link (24hr TTL) |
| Excel workbook | openpyxl (Python) | $1–2 one-time | Supabase Storage link (24hr TTL) |
| Bundle (PDF + Excel) | Both | $2–3 one-time | Both links |

---

## 8. Hosting & Cost Model

The entire platform can run at near-zero cost during development and the first year, scaling cheaply as users arrive.

### Service Providers & Tiers

| Service | Provider | Free Tier | Paid (when scaling) |
|---------|----------|-----------|-------------------|
| Frontend | Vercel | Unlimited personal projects | $20/mo Pro |
| Backend API | Railway | $5/mo free credits | ~$10–30/mo at moderate traffic |
| Database | Supabase | 2 free projects, 500MB | $25/mo Pro |
| Redis cache | Upstash | 10K commands/day free | $0.2 per 100K commands |
| Background jobs | Railway (same dyno) | Included | Scales with backend |
| File storage | Supabase Storage | 1GB free | $0.021/GB |
| Auth | Supabase Auth | 50K MAU free | Included in Pro |
| Payments | Stripe | No monthly fee | 2.9% + $0.30 per transaction |
| Chrome extension | Chrome Web Store | $5 one-time developer fee | Free |
| ML training | Local / GitHub Actions | Free | Free (tabular data is small) |

### Estimated Monthly Cost at Launch

- **0–500 users:** ~$0–10/month (free tiers cover everything)
- **500–2000 users:** ~$30–60/month (Supabase Pro + Railway paid)
- **2000+ users:** ~$100–200/month (scale Railway, Upstash usage)

**Break-even:** ~50 paid draft sessions/month at $2.50 average → $125 gross

---

## 9. Evaluating the Existing Codebase

Before writing new code, the existing PuckLogic codebase should be audited against the architecture described in this document. The audit should answer four questions:

1. **Does a database schema exist?** If so, can it be migrated to Supabase PostgreSQL?
2. **Is there any scraping or data ingestion code?** Can scrapers be salvaged?
3. **Is there existing auth/user management?** Or does it need to be replaced with Supabase Auth?
4. **Is the frontend in React?** If so, components may be portable to Next.js App Router.

### Recommendation

Treat the existing codebase as a reference and parts bin, not a foundation. Given the scope of the re-architecture (new backend framework, new DB, new auth, ML layer, extension), a clean start with selective code salvage will move faster and produce less technical debt than attempting an in-place migration.

### Codebase Audit Checklist

- [ ] Run the existing app locally — does it start?
- [ ] Document what features are partially implemented
- [ ] Identify any scrapers or data pipelines worth keeping
- [ ] Check for existing player data in a DB — migrate if significant
- [ ] Archive the repo as pucklogic-legacy before starting the new build

---

## 10. Phased Roadmap

**Six months to September 2026. Four phases, each producing a shippable milestone.**

### Phase 1: Foundation & Data Pipeline · March – April 2026

- Audit existing codebase; archive and set up new monorepo (Turborepo)
- Scaffold Next.js frontend, FastAPI backend, Supabase project
- Build NHL.com and MoneyPuck scrapers (easiest, most reliable sources)
- Design and seed core DB schema (players, player_stats, player_rankings)
- Set up GitHub Actions cron for daily data refresh
- Basic auth (Supabase Auth — email + Google login)
- Internal admin dashboard to monitor scrape health

### Phase 2: Aggregation Dashboard (Free Tier) · May – June 2026

- Source weight selector UI (drag sliders, preset configs)
- Composite rankings table with sort, filter, positional tabs
- Add NST and Dobber scrapers; user CSV upload for Dom Luszczyszyn
- Redis caching of aggregated results
- User kit save/load (named weighting profiles)
- Stripe integration: checkout flow for export purchases
- PDF and Excel export generation (Celery jobs, Supabase Storage)
- Basic Trends display (raw stats, no ML yet)

### Phase 3: ML Trends Engine · July 2026

- Collect 10+ seasons of historical data (Hockey Reference, MoneyPuck CSVs)
- Feature engineering pipeline (aging curves, linemate quality, situation changes)
- Train and validate XGBoost breakout/regression model
- SHAP explainability integration — show users WHY a player is flagged
- Integrate Trends scores into aggregation dashboard
- Nightly re-scoring Celery job
- Trends tab: breakout candidates list, regression watchlist

### Phase 4: Browser Extension & Launch · August – September 2026

- Chrome MV3 extension scaffold with shadow DOM sidebar
- ESPN Fantasy DOM observer for pick detection
- WebSocket draft session management (backend + extension)
- Real-time best-available suggestion engine
- Extension Stripe payment flow (session activation on web app)
- Elite Prospects scraper (or EP API integration)
- Beta testing with 10–20 real users in mock drafts
- Chrome Web Store submission and approval (allow 2 weeks)
- Public launch — marketing site, Product Hunt post

---

## 11. Key Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| ESPN changes draft room DOM | Medium | High | Multiple selector fallbacks + manual pick entry mode |
| Scraper breaks (site redesign) | High | Medium | Modular scrapers, alerting on failure, manual CSV fallback |
| Dom Luszczyszyn / Athletic paywall | Certain | Low | User paste UI at launch; pursue data agreement later |
| Chrome Web Store rejection | Low | High | Submit 3 weeks early; review MV3 compliance checklist |
| ML model underperforms | Medium | Medium | SHAP transparency helps users calibrate trust; frame as signal not oracle |
| Supabase free tier limits hit | Low at launch | Medium | Upgrade to Pro ($25) is straightforward; budget for it |
| Solo developer bandwidth | High | High | Ruthlessly scope Phase 2 — dashboard ships before extension |

---

## 12. Open Questions for Next Session

1. **Will PuckLogic support custom scoring settings** (Yahoo standard vs custom categories)? This affects how composite rankings are weighted significantly.

2. **Should the free tier require account creation**, or allow anonymous kit building? Anonymous reduces friction but complicates saved kits and upsell tracking.

3. **Is keeper league support different enough from redraft** to need separate UI treatment? Keeper leagues weight young players and contract years differently.

4. **What is the pricing strategy for the draft session** — per-draft purchase, or seasonal subscription that covers all drafts?

5. **Do you want a mobile-responsive web app**, or is desktop-first acceptable for draft day? Drafts are mostly done on desktop but some use phones.

6. **Should the Trends engine have a public-facing blog/explainer** (like MoneyPuck's model page) to build credibility and SEO?

---

## Recommended First Week Tasks

1. Run `git clone` on the existing PuckLogic repo and audit it (1–2 hours)
2. Create a new Supabase project and define the core schema
3. Scaffold the Turborepo monorepo: apps/web (Next.js) + apps/api (FastAPI)
4. Write the NHL.com stats scraper — this is the cleanest starting point
5. Set up a GitHub Actions workflow to run the scraper on a daily cron
