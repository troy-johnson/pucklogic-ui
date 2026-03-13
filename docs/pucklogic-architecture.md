# PuckLogic Draft Kit — Architecture Reference

**March 2026 · Confidential**

*System-level architecture, decisions, and data flow. For implementation details, see the domain-specific reference docs:*

- **[backend-reference.md](backend-reference.md)** — Full SQL DDL, API routes, security model, scraper patterns, ML serving
- **[frontend-reference.md](frontend-reference.md)** — App Router pages, Zustand stores, components, auth flow, scoring UI
- **[extension-reference.md](extension-reference.md)** — Platform adapters, WebSocket protocol, manifest, auth handoff

*Phase scope and task tracking live in Notion, not in docs. Docs describe what and how; Notion cards describe when and scope.*

---

## 1. Product Summary

PuckLogic is a fantasy hockey platform with three components:

1. **Rankings Aggregation Dashboard** (free tier) — user-weighted consensus rankings from multiple sources, with PDF/Excel export ($2–3 one-time)
2. **Real-Time Draft Monitor** (paid) — Chrome MV3 extension for ESPN + Yahoo Fantasy, $2.99 per draft session
3. **ML Trends Engine** — breakout candidate identification and regression risk flagging using XGBoost

**Target users:** Casual redraft + competitive keeper league players
**Formats:** H2H, rotisserie, keeper, redraft (format-agnostic)
**Scope at launch:** Skaters only (no goalies), ESPN + Yahoo (no Sleeper), desktop-first dashboard (mobile-responsive) with desktop-only draft monitor

---

## 2. Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Frontend | Next.js 14+ (App Router), Turborepo monorepo | Shared React components with extension |
| Styling | Tailwind CSS + shadcn/ui | Mobile-responsive from day one |
| State | Zustand | Lightweight, no boilerplate |
| Data fetching | SWR or React Query (client), Server Components (SSR) | |
| Backend | FastAPI (Python) on Railway/Fly.io | ML model + API in same process |
| Database | Supabase (PostgreSQL + Auth + Storage) | Built-in auth, RLS, file storage |
| Caching | Upstash Redis | 6-hour TTL on rankings |
| Background jobs | Celery + Redis | Exports, nightly re-scoring |
| ML | XGBoost / LightGBM, SHAP for explainability | Interpretable, fast on tabular data |
| Experiment tracking | MLflow (local → Fly.io) | |
| Payments | Stripe Checkout (web app only) | Chrome Web Store compliance |
| Extension | Chrome MV3, shadow DOM sidebar | ESPN + Yahoo via platform adapter pattern |
| Frontend hosting | Vercel | |
| Backend hosting | Railway or Fly.io | |

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│ DATA SOURCES                                            │
│ NHL.com API · MoneyPuck CSVs · NST (scraped)           │
│ Dobber (scraped) · Dom/Athletic (user CSV paste)       │
│ Hockey Reference · Evolving Hockey ($5/mo)             │
│ Elite Prospects · NHL EDGE API                          │
└──────────────────────┬──────────────────────────────────┘
                       │ Scrapers + Parsers (Python)
                       │ Player name/ID matching system
┌──────────────────────▼──────────────────────────────────┐
│ INGESTION PIPELINE                                      │
│ GitHub Actions cron · Staging table pattern             │
│ Supabase PostgreSQL · Redis cache (Upstash)            │
│ Failure handling: serve stale + alert on failure        │
└──────────────────────┬──────────────────────────────────┘
                       │ REST + WebSocket
┌──────────────────────▼──────────────────────────────────┐
│ FASTAPI BACKEND                                         │
│ Rankings aggregation · Trends ML inference              │
│ Scoring translation layer (raw stats → fantasy pts)    │
│ Export generation · Auth (Supabase JWT)                 │
│ Stripe webhooks · Draft session state                  │
│ Anonymous session management                            │
└────────┬──────────────────────────────┬─────────────────┘
         │ HTTPS / REST                 │ WebSocket
┌────────▼───────────┐  ┌──────────────▼──────────────────┐
│ NEXT.JS WEB APP    │  │ CHROME EXTENSION (MV3)          │
│ Free dashboard     │  │ Paid — $2.99 / draft session    │
│ Mobile-responsive  │  │ ESPN + Yahoo Fantasy overlay    │
│ Anonymous kit build│  │ Platform adapter pattern        │
│ Export checkout    │  │ Desktop-only                     │
│ Scoring config UI  │  │ Manual fallback mode            │
└────────────────────┘  └─────────────────────────────────┘
```

---

## 4. Database Schema

> Full SQL DDL and RLS policies: [backend-reference.md § Database Schema](backend-reference.md)

### Core Tables (public read)

- **players** — NHL player master (id, name, team, position, date_of_birth, nhl_id)
- **player_aliases** — name variant mapping for cross-source matching (alias, canonical_player_id, source)
- **player_rankings** — per-source rankings (player_id, source_id FK, rank, score, season, scraped_at)
- **player_rankings_staging** — staging table for scraper writes (same schema, promoted on success)
- **player_stats** — raw stats per season (goals, assists, TOI, CF%, xGF%, iSCF/60, SH%, PDO, etc.)
- **player_trends** — ML output (breakout_score, regression_risk, confidence, shap_values JSONB, season); UNIQUE(player_id, season)
- **player_projections** — projected stats per season (projected_stats JSONB, scoring_basis); UNIQUE(player_id, season)
- **sources** — registered aggregation sources (name, url, scrape_config, active, last_successful_scrape)

### User Tables

- **user_kits** — saved user weighting configs (user_id OR session_token, source_weights JSONB, scoring_config_id FK, name)
- **scoring_configs** — fantasy scoring presets and custom configs (id, name, stat_weights JSONB, is_preset)
- **draft_sessions** — live draft state (user_id, platform, league_config, picks[], available[], kit_id, status)
- **exports** — export job records (user_id, type, status, storage_url)
- **subscriptions** — Stripe subscription state (user_id, stripe_session_id, plan, status, expires_at)

### Security Enforcement Model

The backend uses `SUPABASE_SERVICE_ROLE_KEY`, which bypasses RLS. Security enforcement is split:

- **RLS (public read):** Public tables (players, player_rankings, player_stats, player_trends, player_projections, sources) allow SELECT for all roles including anonymous. Preset scoring_configs (where `is_preset = true`) allow public SELECT.
- **API-layer ownership checks:** All user-owned data (user_kits, draft_sessions, exports, subscriptions, custom scoring_configs) is protected by explicit ownership assertions in every FastAPI endpoint. The API checks `user_id` match (or `session_token` match for anonymous kits).
- **Service-role writes only:** All INSERT/UPDATE/DELETE on public tables is restricted to the service role (scrapers, ML jobs).

See [backend-reference.md § Security Model](backend-reference.md) for per-table, per-endpoint enforcement details.

---

## 5. Key Algorithms & Systems

### 5.1 Rankings Aggregation

- Each source assigns a rank (1 = best), normalized to 0–1 score
- User-defined weights (summing to 1.0) applied to each source score
- Weighted average produces composite score, sorted descending
- Missing source data: weight redistributed to present sources
- Cached in Redis for 6 hours; manual refresh rate-limited (10 req/min per user, IP-based for anon)

### 5.2 Player Name/ID Matching

- NHL player ID is canonical key
- player_aliases table maps variant names to canonical IDs
- Ingestion pipeline: exact match → fuzzy match (rapidfuzz, >90% similarity) → flag for manual review
- Admin dashboard surfaces unmatched players with suggested matches
- Runs at ingestion time, not query time

### 5.3 Scraper Failure Handling

- Scrapers write to staging tables
- On full success: atomic swap to production (DELETE old + INSERT new in transaction)
- On failure: staging discarded, production unchanged, stale data served with "last updated" badge
- GitHub Actions sends failure notification (email/Slack webhook)

### 5.4 Anonymous-to-Authenticated Migration

- Anonymous users build kits keyed by session token (UUID in cookie)
- On sign-up/login: session-keyed kits auto-transfer to user_id
- Anonymous kits expire after 7 days (cron cleanup)
- UI nudge: persistent banner "Sign up to save this kit"

### 5.5 Scoring Translation Layer

- Model predicts REAL production trajectory (not fantasy-specific)
- Breakout = +20% increase in rate-adjusted production (G, A1, SOG/60, TOI) vs trailing 2-season avg
- Scoring presets: ESPN Standard H2H, Yahoo Standard, Rotisserie, Custom
- Translation: sum(predicted_stat_i × weight_i) for all categories
- Dashboard shows both raw projected stats AND fantasy points side by side

---

## 6. ML Trends Engine

### 6.1 Model

- XGBoost or LightGBM (gradient boosted trees)
- Training data: 2008–2025 (10+ seasons, 5000+ player-season records)
- Validation: 2023–2025 (recent, unseen data)
- SHAP for feature importance and user-facing explainability
- Pre-computed SHAP values stored (not computed nightly)

### 6.2 Feature Groups

1. **Production history:** G, A, Pts, PPP per 60 — last 3 seasons
2. **Usage/deployment:** TOI/game, PP time, zone starts, line position
3. **Efficiency metrics:** xGF%, CF%, HDCF%, on-ice SH% vs career SH%, iSCF/60
4. **Aging curves:** Age, years in league, historical comps at same age
5. **Injury history:** Games missed per season, injury type, recency
6. **Linemate quality:** Teammates' average xGF%, line combination history
7. **Contract context:** Contract year (motivation proxy), entry-level vs vet
8. **Situation changes:** Team trade activity, coach change, PP role shift

### 6.3 Key Signals

- **Breakout detection:** iSCF/60 emphasis (most underutilized predictive stat), rising xGF% with suppressed production, age-curve inflection points
- **Regression detection (3-part signal):**
  1. G-minus-ixG gap (scoring above expected)
  2. SH% vs career average + 2 std devs (unsustainable shooting)
  3. PDO > 1.03 (historically mean-reverts)
- **Excluded metrics:** takeaways/giveaways (arena scorer bias), plus/minus (structural flaws)

### 6.4 Label Definition (UPDATED)

- Breakout: +20% increase in rate-adjusted real production vs trailing 2-season average
- Regression: -20% decline in rate-adjusted real production
- Fantasy scoring applied as downstream translation layer, NOT part of model training

### 6.5 Serving

- Serialized with joblib, loaded in FastAPI process at startup
- Inference: <10ms per player, synchronous
- Batch re-scoring: nightly Celery task → player_trends table
- Retraining: yearly pre-season
- Mid-season updates: nightly re-scoring Oct–Mar

### 6.6 Data Sources for Training

- Hockey Reference (season-level stats, free)
- MoneyPuck (CSV archives, xG data from 2015+, free)
- Natural Stat Trick (historical game logs, advanced stats from 2008+)
- Evolving Hockey ($5/mo, WAR/RAPM data) — subscribe before Phase 3
- CapFriendly/PuckPedia (contract status, situation changes)

---

## 7. Browser Extension Architecture

### 7.1 Platform Adapter Pattern

```
PlatformAdapter interface:
  detectPicks()          — set up MutationObserver for platform's draft room
  extractPlayerName(el)  — extract player name from pick DOM element
  getDraftRoomState()    — return current draft state (round, pick #)
  getLeagueConfig()      — auto-detect league format from DOM

ESPNAdapter implements PlatformAdapter
YahooAdapter implements PlatformAdapter

Content script: check window.location.hostname → load correct adapter
```

### 7.2 Component Map

- **manifest.json** — MV3 manifest, host permissions for espncdn.com + Yahoo Fantasy
- **content_script.js** — Injected into draft room, loads platform adapter, observes DOM
- **sidebar.jsx** — React component (shadow DOM isolation)
- **background.js** — Service worker, manages WebSocket to backend (reconnection with exponential backoff)
- **popup.jsx** — Extension popup (login, kit selection, session start)
- **shared/components** — From Turborepo packages/ui

### 7.3 Pick Detection

- MutationObserver with 3–5 selector fallbacks per platform
- Manual fallback: "Mark Pick" button in sidebar
- Player names matched against PuckLogic canonical IDs
- Test fixtures maintained for both ESPN and Yahoo draft rooms

### 7.4 Real-Time Suggestions

- On clock: top N available players from backend ranked by user's weighted kit
- Filtered by positional need (default 5% weighting, adjustable 0–10%)
- Contrast rankings: show how other services ranked each suggestion
- Offline fallback: cache suggestions when WebSocket fails

### 7.5 Monetization Flow

- Extension free to install, requires auth
- $2.99 per draft session (pay on web app via Stripe Checkout)
- Web app writes active session token to Supabase
- Extension polls for token at startup
- No payment UI in extension (Chrome Web Store compliance)
- A/B test $1.99 vs $3.99 post-launch

---

## 8. Data Ingestion Pipeline

| Source | Method | Frequency | Notes |
|--------|--------|-----------|-------|
| NHL.com stats | Official API (free) | Daily | Most reliable |
| Natural Stat Trick | HTML scraper (BeautifulSoup) | Daily | Rate limit 1 req/sec, respect robots.txt |
| MoneyPuck | CSV downloads | Daily | Free, no auth |
| Dobber Hockey | HTML scraper | Weekly pre-season | May need Playwright for JS-rendered content |
| Dom Luszczyszyn | User CSV paste | Weekly pre-season | Paywalled — no scraping |
| Elite Prospects | HTML scraper + EP API | Weekly | EP API preferred if budget allows |
| Evolving Hockey | Manual CSV download | Phase 3 only | $5/mo subscription |

No formal partnerships at launch. Scraping + public CSVs only. Revisit partnerships if product gains traction.

---

## 9. Export Generation

| Type | Library | Price | Delivery |
|------|---------|-------|----------|
| PDF cheat sheet | WeasyPrint | $1–2 | Supabase Storage (24hr TTL) |
| Excel workbook | openpyxl | $1–2 | Supabase Storage (24hr TTL) |
| Bundle (PDF + Excel) | Both | $2–3 | Both links |

Generated async via Celery. Multi-tab Excel: master rankings, by-position, Trends tab with breakout/regression scores.

---

## 10. Hosting & Cost Model

| Service | Provider | Free Tier | Paid (scaling) |
|---------|----------|-----------|----------------|
| Frontend | Vercel | Unlimited personal | $20/mo Pro |
| Backend | Railway | $5/mo credits | ~$10–30/mo |
| Database | Supabase | 500MB (upgrade in Phase 3) | $25/mo Pro |
| Redis | Upstash | 10K cmd/day | $0.2/100K |
| File storage | Supabase Storage | 1GB | $0.021/GB |
| Auth | Supabase Auth | 50K MAU | Included |
| Payments | Stripe | No monthly fee | 2.9% + $0.30/tx |
| Extension | Chrome Web Store | $5 one-time | Free |
| ML training | Local/GitHub Actions | Free | Free |

**Break-even:** ~50 draft sessions/month at $2.50 avg = $125 gross

---

## 11. Phased Roadmap (Revised for nights-and-weekends)

| Phase | Window | Cards | Hours | Key Milestones |
|-------|--------|-------|-------|----------------|
| Phase 1: Foundation | Mar–May 2026 | 11 | ~32 | Data pipeline live, player matching, RLS, scraper fallbacks |
| Phase 2: Dashboard | Jun–Jul 2026 | 14 | ~43 | Free dashboard, anonymous kits, scoring config, exports |
| Phase 3: ML Engine | Aug 2026 | 8 | ~32 | Model trained, Trends tab live, nightly re-scoring |
| Phase 4: Extension | Sep–Oct 2026 | 13 | ~49 | ESPN + Yahoo adapters, beta, privacy policy, launch |
| **TOTAL** | | **46** | **~156** | **Launch: late October 2026** |

**Alternative strategy:** Launch Phases 1–3 (dashboard + Trends) as standalone web product in September, release extension as separate launch in October. Two marketing moments, reduced launch-day risk.

---

## 12. Key Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| ESPN/Yahoo DOM changes | Medium | High | Platform adapter pattern, 3–5 selector fallbacks, manual mode, test fixtures |
| Scraper breaks (site redesign) | High | Medium | Modular scrapers, staging table pattern, stale data with badge, manual CSV fallback |
| Athletic paywall | Certain | Low | User CSV paste at launch; pursue data agreement later |
| Chrome Web Store rejection | Low | High | Submit 3 weeks early, privacy policy, MV3 compliance |
| ML model underperforms | Medium | Medium | SHAP transparency, frame as signal not oracle |
| Supabase 500MB limit | Medium (Phase 3) | Medium | Budget for $25/mo Pro from Phase 3 onward |
| MV3 service worker termination | Medium | Medium | WebSocket reconnection with exponential backoff, offline suggestion cache |
| Solo developer bandwidth | High | High | Adjusted timeline (late Oct), phase boundaries, no rushing |

---

## 13. Open Decisions

| Question | Decide By | Notes |
|----------|-----------|-------|
| Keeper league UI treatment | End of Phase 2 | Same UI with extra columns vs. dedicated keeper mode. Affects ML labels if keeper mode re-weights. |
| Custom scoring presets scope | Mid-Phase 2 | How many presets, how deep the custom editor goes. Can be simple at launch. |

---

## 14. Post-Launch Backlog (v1.1+)

- Public model explainer page (after model validated against real season)
- Sleeper platform adapter
- Goalie support
- Custom scoring re-sort (rankings sorted by projected fantasy value)
- Keeper league dedicated UI (if decided)
- Mobile draft companion (non-extension, web-based)
- Data source partnerships (NST, MoneyPuck)
- A/B pricing tests ($1.99 vs $3.99)
