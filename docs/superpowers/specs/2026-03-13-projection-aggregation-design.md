# Projection Aggregation System — Design Spec

**Date:** 2026-03-13
**Status:** Approved
**Scope:** v1.0 (Phase 2 redesign + Phase 3 export)

---

## Background & Motivation

The original aggregation pipeline stored per-source **rank positions** in `player_rankings` and computed a composite rank by normalizing and blending those positions. This was incorrect.

PuckLogic is a **stat projection aggregator**. Sources (Dobber, HashtagHockey, Apples & Ginos, etc.) publish pre-season **projected counting stats** (G, A, PIM, SOG, hits, blocks, TOI, PP stats, etc.). The correct pipeline is:

1. Ingest per-source projected stats into `player_projections`
2. Compute a weighted average of each stat across sources
3. Apply the user's league scoring settings to the aggregated stats → projected fantasy points
4. Compute VORP relative to replacement-level players at each position
5. Attach schedule score (off-night game count) as a supplementary value signal
6. Sort by projected fantasy points descending

The `player_rankings` table is retained for potential future rank-only sources but is removed from the aggregation pipeline. NHL.com and MoneyPuck write to `player_stats` only.

---

## Section 1: Data Model

### `player_projections` — redesigned

Add `source_id` FK. Change unique constraint from `(player_id, season)` to `(player_id, source_id, season)`.

**Fixed stat columns (all nullable — null means source did not project this stat):**

| Skater stats | Goalie stats |
|---|---|
| `g` integer | `gs` integer |
| `a` integer | `w` integer |
| `plus_minus` integer | `l` integer |
| `pim` integer | `ga` integer |
| `ppg` integer | `sa` integer |
| `ppa` integer | `sv` integer |
| `ppp` integer | `sv_pct` float |
| `shg` integer | `so` integer |
| `sha` integer | `otl` integer |
| `shp` integer | |
| `sog` integer | |
| `fow` integer | |
| `fol` integer | |
| `hits` integer | |
| `blocks` integer | |
| `gp` integer | |

**Additional columns:**
- `extra_stats` JSONB — overflow for source-specific stats not in the fixed set
- `updated_at` timestamptz

**Null semantics:** `null` means no projection (displayed as `—`). `0` means projected at zero. These are distinct and must not be conflated.

**PPP / SHP double-counting warning:** `ppp = ppg + ppa` and `shp = shg + sha` by definition. A `scoring_config` must not assign non-zero weights to both `ppp` and `ppg`/`ppa` simultaneously (same for `shp`/`shg`/`sha`) — doing so double-counts. Validation: at `scoring_config` creation time, the API must reject any config where `ppp > 0` and either `ppg > 0` or `ppa > 0`, and similarly for `shp`/`shg`/`sha`. All three columns are stored for display purposes; scoring applies only one level of granularity.

---

### `scoring_configs` — existing table (extended reference)

The existing `scoring_configs` table schema relevant to this pipeline:

```sql
create table scoring_configs (
  id            uuid primary key default gen_random_uuid(),
  name          text not null,
  stat_weights  jsonb not null,  -- keys must match player_projections column names
  is_preset     boolean not null default false,
  user_id       uuid,            -- null = system preset
  created_at    timestamptz not null default now()
);
```

`stat_weights` keys must exactly match `player_projections` fixed stat column names (e.g. `"g"`, `"a"`, `"ppp"`, `"sog"`). The `apply_scoring_config(stats, scoring_config)` function iterates over `stat_weights` keys; unrecognized keys are ignored. Missing keys default to weight `0`.

Seeded presets cover standard ESPN/Yahoo/Fantrax point configurations. PPP/SHP double-counting validation (described above) is enforced at config creation for both presets and user-defined configs.

---

### `schedule_scores` — new table

One row per player per season. Populated once per season from the NHL schedule API; refreshed if the schedule changes.

| column | type | notes |
|---|---|---|
| `player_id` | uuid FK | |
| `season` | text | e.g. `"2025-26"` |
| `off_night_games` | integer | team games on nights where < 16 NHL teams play |
| `total_games` | integer | projected GP for the season |
| `schedule_score` | float | min-max normalized 0–1 across all active skaters |
| unique | `(player_id, season)` | |

**"Off night"** = a calendar date where fewer than 16 of 32 NHL teams are playing. Computed from `api.nhle.com` schedule — no external scraping needed.

**Normalization formula:**
`schedule_score = (off_night_games − min_off_nights) / (max_off_nights − min_off_nights)`

Where min/max are taken across all players with projected GP > 0 for the season. Skaters and goalies are normalized together. If all players have the same `off_night_games` (degenerate case), all scores default to `0.5`. When the schedule changes mid-season, all `schedule_scores` for that season are recomputed in full.

---

### `player_platform_positions` — new table

Platform-specific position eligibility. Separate from `players.position` because eligibility differs across fantasy platforms (e.g. a player may be LW/RW on Yahoo but LW only on Fantrax).

| column | type | notes |
|---|---|---|
| `player_id` | uuid FK | |
| `platform` | text | `"espn"`, `"yahoo"`, `"fantrax"` |
| `positions` | text[] | e.g. `["LW", "RW"]` |
| unique | `(player_id, platform)` | |

`players.position` remains the NHL.com canonical default position (C, LW, RW, D, G). Dual eligibility is derived at query time: `len(positions) > 1` for the user's platform.

---

### `sources` — additions

- `default_weight` float — PuckLogic Recommended default weight for this source
- `is_paid` boolean — marks paywalled or premium sources
- `user_id` uuid FK (nullable) — set for user-uploaded custom sources; null for system sources

**Custom source privacy:** Any `sources` row with `user_id` set is private to that user. It must not appear in other users' source lists or aggregation queries. The API enforces this by filtering `sources` to `user_id IS NULL OR user_id = current_user.id` on every request.

**2-custom-source limit:** Enforced at upload time by counting `sources` rows where `user_id = current_user.id`. If count ≥ 2, reject the upload with HTTP 409 and a clear message.

**Default weight behavior:** New users get a "PuckLogic Recommended" preset that uses curated `default_weight` values reflecting historical projection accuracy. Equal weights (1.0 for all) available as a one-click reset. Recommended defaults provide immediate value and serve as a conversion driver for new users.

**Paid source display:**
- Owner account: all sources enabled, full data in rankings, PDF, Excel, and extension
- Public users: paid source stat columns are present but empty — aggregation runs over free sources only, clearly indicated in the UI
- User-uploaded custom sources: private to that user, treated as paid

---

### `league_profiles` — new table

Complete league configuration needed to compute fantasy points and VORP.

| column | type | notes |
|---|---|---|
| `id` | uuid PK | |
| `user_id` | uuid FK | owner |
| `name` | text | e.g. `"My ESPN H2H League"` |
| `platform` | text | `"espn"`, `"yahoo"`, `"fantrax"` |
| `num_teams` | integer | e.g. 12 |
| `roster_slots` | jsonb | `{"C":2,"LW":2,"RW":2,"D":4,"G":2,"UTIL":1,"BN":4}` |
| `scoring_config_id` | uuid FK | points values per stat |
| `created_at` | timestamptz | |

**Relationship to `user_kits`:** `league_profiles` stores stable league structure (platform, teams, roster composition, scoring). `user_kits` stores named source weight presets — reusable across leagues or as saved weight experiments. They are separate: a user configures one league profile and experiments with many source weight combinations.

---

### `players` — NHL.com authority

`players.position` is the NHL.com canonical position — authoritative, never overwritten by other sources. All other sources map player IDs and names *to* NHL.com records, never the reverse.

---

## Section 2: Aggregation Pipeline

### Endpoint: `POST /rankings/compute`

**Request:**
```json
{
  "season": "2025-26",
  "source_weights": {"dobber": 10, "hashtag_hockey": 5, "apples_ginos": 5},
  "scoring_config_id": "uuid",
  "platform": "yahoo",
  "league_profile_id": "uuid"
}
```

`league_profile_id` is optional. If omitted, VORP is excluded from the response. If provided, the endpoint verifies `league_profiles.user_id = current_user.id` before use; returns HTTP 403 if the profile belongs to another user.

**Pipeline steps:**

1. **Fetch** all `player_projections` rows for the season, joined with `sources` (filtered to `user_id IS NULL OR user_id = current_user.id`), `players`, and `player_platform_positions` for the requested platform
2. **Weighted average per stat** — for each player, for each stat:
   `projected_stat = SUM(stat × source_weight) / SUM(weights for sources that have this stat)`
   Nulls are excluded per-stat. A source projecting 30G but no hits contributes to the goals average but not the hits average. Result is `null` only if *no* source projected that stat.
3. **Apply scoring config** — `projected_fantasy_points = SUM(projected_stat × scoring_config.stat_weights[stat])` across all stats. Null stats contribute 0 to the sum.
4. **Compute VORP** (if `league_profile_id` provided):
   - **Primary position for VORP:** use `players.position` (NHL.com canonical) as the authoritative position group for replacement-level calculation. Platform positions are used for display and eligibility only.
   - For each position group, find replacement level = the Nth ranked player where N = `(num_teams × position_slots) + 1`
   - If fewer than N players exist for a position, use the last available player as replacement level
   - If a position group has zero players, `vorp = null` for all players in that group
   - If a player's `projected_fantasy_points` is null (all stats null), their `vorp = null`
   - VORP values may be negative — a below-replacement player has negative VORP; do not clamp at 0
   - `vorp = player_projected_fantasy_points − replacement_level_projected_fantasy_points`
5. **Attach schedule score** from `schedule_scores` — supplementary field, not added to fantasy points. If missing, both fields are `null`.
6. **Sort** by `projected_fantasy_points` descending. Players with null fantasy points sort last.
7. **Cache** result in Redis, 6h TTL. Cache key format: `rankings:{season}:{digest}` where digest is a stable SHA-256 hash of `(source_weights_sorted, scoring_config_id, platform, league_profile_id)`. The `{season}` prefix is preserved so that `invalidate_rankings(season)` can pattern-delete `rankings:{season}:*` and cover all variants. `CacheService` must be updated to accept the full parameter set and produce this key format.

**Response per player:**
```json
{
  "composite_rank": 1,
  "player_id": "uuid",
  "name": "Connor McDavid",
  "team": "EDM",
  "default_position": "C",
  "platform_positions": ["C", "LW"],
  "projected_fantasy_points": 387.5,
  "vorp": 156.2,
  "schedule_score": 0.82,
  "off_night_games": 24,
  "source_count": 6,
  "projected_stats": {
    "g": 52, "a": 78, "plus_minus": 22, "pim": 28,
    "ppg": 18, "ppa": 24, "ppp": 32,
    "shg": 1, "sha": 2, "shp": 3,
    "sog": 315, "fow": 820, "fol": 680,
    "hits": 45, "blocks": 32, "gp": 78
  }
}
```

All stat fields present for every player. Unprojected stats are `null`, displayed as `—` in UI and exports.

**Cache invalidation:** When a new source ingest completes for a season, call `cache.invalidate_rankings(season)` which pattern-deletes all keys matching `rankings:{season}:*`.

---

### Scraper contract

**`BaseProjectionScraper`** — new ABC, separate from the existing `BaseScraper`:

```python
class BaseProjectionScraper(ABC):
    SOURCE_NAME: str
    DISPLAY_NAME: str

    @abstractmethod
    async def scrape(self, season: str, db: Client) -> int:
        """Fetch projections, resolve player names, write to player_projections.
        Returns count of rows upserted."""
        ...
```

The existing `BaseScraper` subclasses (`NhlComScraper`, `MoneyPuckScraper`) are updated to write to `player_stats` instead of `player_rankings`. They remain `BaseScraper` subclasses — they are not projection scrapers. New projection source scrapers (HashtagHockey, DailyFaceoff, etc.) subclass `BaseProjectionScraper`.

---

### Services

- `services/projections.py`
  - `aggregate_projections(rows, source_weights, scoring_config) → list[AggregatedPlayer]`
  - `compute_weighted_stats(player_rows, source_weights) → dict[str, float | None]`
  - `apply_scoring_config(stats, scoring_config) → float`
  - `compute_vorp(players, league_profile) → dict[str, float | None]`
- `repositories/projections.py`
  - `get_by_season(season, platform, user_id) → list[ProjectionRow]`

---

### Updated schemas

`ExportRequest` and `RankingsComputeRequest` are updated to include:
- `scoring_config_id: str`
- `platform: str`
- `league_profile_id: str | None`

The existing `weights: dict[str, float]` field is renamed to `source_weights` for clarity. `services/exports.py` `generate_excel()` and `generate_pdf()` are updated to accept and render the new output shape (fantasy points, VORP, off-night games, full stat columns).

---

## Section 3: Ingestion

### Two paths, one contract

All projection sources — whether auto-scraped or user-uploaded — implement `BaseProjectionScraper`. Auto-scrapers implement it directly. The paste/upload handler parses CSV/Excel and feeds into the same contract.

### Source classification

| Source | Type | Ingest method | Paid |
|---|---|---|---|
| HashtagHockey | Projection | Auto-scrape | No |
| DailyFaceoff | Projection | Auto-scrape | No |
| Apples & Ginos | Projection | Auto-scrape | No |
| LineupExperts | Projection | Auto-scrape | No |
| Yahoo | Projection | Auto-scrape / API | No |
| Fantrax | Projection | Auto-scrape / API | No |
| DatsyukToZetterberg | Projection | Paste / upload | No |
| Bangers Fantasy Hockey | Projection | Paste / upload | No |
| KUBOTA | Projection | Paste / upload | No |
| Scott Cullen | Projection | Paste / upload | No |
| Steve Laidlaw | Projection | Paste / upload | No |
| Dom Luszczyszyn | Projection | Paste / upload | Yes |
| NHL.com | Actual stats | Auto-scrape | No |
| MoneyPuck | Actual stats (advanced) | Auto-scrape | No |

**NHL.com** → `player_stats` (counting stats: G, A, PTS, PIM, SOG, TOI, GP, PPP, SHP)
**MoneyPuck** → `player_stats` (advanced: CF%, xGF%, I_F_xGoals, PDO, SH%)
Neither writes to `player_projections` by default. They optionally appear as a "last-season baseline" projection source only if the user explicitly enables them.

### Custom user uploads

Users get 2 custom projection source slots on the Create Draft Kit dashboard:
- Name the source (e.g. "Dom Luszczyszyn")
- Upload CSV or Excel
- Map columns to canonical stat names via a simple mapping UI
- Ingested into `player_projections` with a user-owned `sources` row (`sources.user_id = current_user.id`, `sources.is_paid = true`)
- Private to that user; maximum 2 active custom sources enforced at upload
- Can be replaced at any time; replacement triggers `invalidate_rankings(season)` for that user's cached results

All aggregation math happens server-side. The exported Excel and PDF are read-only outputs — no import slots, no embedded formulas for custom sources.

### Schedule ingestion

One GitHub Actions job per season, re-run if schedule changes:
1. Fetch full NHL season schedule from `api.nhle.com`
2. For each game date, count how many teams are playing
3. Flag dates where < 16 teams play as "off nights"
4. For each player, count their team's games on off nights
5. Compute `schedule_score` using min-max normalization across all players with GP > 0
6. Write to `schedule_scores`, upsert on `(player_id, season)`
7. When the schedule changes, recompute all rows for that season in full

### Name resolution

At ingest time, every source player name is fuzzy-matched against `players.name` (NHL.com canonical) using `scrapers/matching.py` (rapidfuzz):
- Confidence ≥ threshold → write row with resolved `player_id`
- Confidence < threshold → log to `scraper_logs` with unmatched name, skip row
- After each ingest job: surface summary to dashboard — e.g. "847 matched, 12 unmatched — review"
- No silent drops

---

## Section 4: Error Handling & Edge Cases

| Scenario | Behavior |
|---|---|
| Name match fails | Log to `scraper_logs`, skip row, surface summary after ingest |
| Source upload invalid (bad columns, non-numeric stats) | Reject entire file with clear error message; never partial-ingest |
| Stat not projected by any source | `projected_stat = null`, displayed as `—`, not `0` |
| Schedule scores not yet populated | `off_night_games = null`, `schedule_score = null`; rankings compute normally |
| No `league_profile_id` in request | `vorp = null` on all players; rankings sort by fantasy points normally |
| `league_profile_id` belongs to another user | HTTP 403 |
| Fewer players than replacement threshold at a position | Use last available player as replacement level |
| Zero players at a position | `vorp = null` for all players in that position group |
| Player has all-null projected stats | `projected_fantasy_points = null`, `vorp = null`; player sorts last |
| VORP is negative | Allowed — below-replacement players have negative VORP; do not clamp at 0 |
| All source weights are zero | HTTP 400: "At least one source must have weight > 0" |
| New source ingest completes | `invalidate_rankings(season)` — pattern-delete `rankings:{season}:*` |
| Paid source, public user | Stat columns present but empty; aggregation uses free sources only |
| Custom source limit exceeded | HTTP 409: "Maximum 2 custom sources per user" |
| PPP + PPG/PPA both non-zero in scoring config | HTTP 400 at config creation: "Cannot score both PPP and PPG/PPA simultaneously" |

---

## Section 5: Export

### Excel — Draft Kit

Two sheets:

**Sheet 1 — Full Rankings**
Columns: ADP (blank — v1.0 placeholder, no data source yet), TAKEN (user marks `X`), PLAYER, TEAM, POS, FanPts, FP/GP, VORP, PRNK (positional rank), GP, OFF (off-night games), then full stat columns (skater stats grouped, then goalie stats grouped; each player only shows their relevant stats).

TAKEN column uses conditional formatting: marking `X` greys out and strikes through the row.

**Note on ADP:** ADP (Average Draft Position) is displayed as a blank column in v1.0. A data source (NFBC, Yahoo, or Fantrax ADP) must be identified and an ingestion path defined before v1.0 ships or ADP is removed from the spec entirely. This is flagged as a pre-launch decision.

**Sheet 2 — Best Available**
Position-grouped view: CENTER, LEFT WING, RIGHT WING, DEFENSE, GOALIES, MULTI-POSITIONAL. Each group shows top remaining players (PLAYER, POS, FanPts, VORP, ADP). Driven by Excel `FILTER` formulas referencing Sheet 1's TAKEN column — no VBA, works in Excel and Google Sheets.

Header block: league settings, source weights used, PuckLogic Recommended flag, generated date and season.

### PDF — Printable Draft Sheet

Clearly labeled "Print & Draft" — designed for offline drafts with no device access:
- Full player rankings with a blank checkbox column for pen-marking taken players
- Static best available summary by position (snapshot at export time)
- League settings and source weights printed at top
- Generated date and season

Users may export both PDF and Excel as many times as they want, with any weight configuration, at no additional cost.

---

## Section 6: Phase 4 Notes (Out of Scope for This Spec)

The following features depend on this spec's data foundation but are designed and implemented in Phase 4 (Chrome Extension):

- **Positional need tracking** — draft extension monitors which roster slots the user has filled and surfaces best-available recommendations weighted by remaining positional need (e.g. if all forwards are drafted, D and G rise in priority)
- **0G strategy toggle** — de-prioritizes goalies in draft recommendations; user opts in to not spending a premium pick on a goalie given year-to-year goalie volatility
- **Dual eligibility value boost** — players with multiple platform positions get a value multiplier in draft recommendations reflecting roster flexibility

These require `player_platform_positions` and `league_profiles.roster_slots`, both defined in this spec.

---

## Notion Tasks to Create

After this spec is approved, create Notion cards for:

1. **Phase 4 — Draft extension: positional need tracking + 0G strategy** (links to Section 6 above)
2. **ADP data source decision** — identify provider (NFBC, Yahoo, Fantrax) and define ingestion path before v1.0 launch
3. **Update sources table** — add `is_paid`, `default_weight`, `user_id` columns
4. **Build custom projection upload UI** — 2 slots, column mapping, validation
5. **Build schedule ingestion job** — NHL schedule API → `schedule_scores`
6. **Build `player_platform_positions` ingestion** — per-platform position eligibility
7. **Migrate NHL.com + MoneyPuck scrapers** — write to `player_stats` instead of `player_rankings`
8. **Build `BaseProjectionScraper`** — new ABC for projection source scrapers

---

## Section 7: Spec Patch Notes (2026-03-14)

These notes resolve open implementation gaps identified during post-approval review.

### 7.1 `source_weights` key contract and validation

`source_weights` keys must use `sources.name` (slug), not display name or UUID.

- Example: `{ "hashtag_hockey": 5, "apples_ginos": 5 }`
- Keys are matched exactly (case-sensitive) against visible rows in `sources`
- Unknown keys are rejected with HTTP 400: `Unknown source key: {key}`
- Keys that reference inaccessible sources (another user's custom source) are rejected with HTTP 400
- Validation runs before aggregation; request fails fast on the first invalid key

### 7.2 Response field semantics: `source_count`

`source_count` is defined as the number of weighted sources that contributed at least one non-null projected stat for the player in the requested season.

Inclusion criteria:
- Source exists in `source_weights` with weight > 0
- Source has a `player_projections` row for that player/season
- That row contains at least one non-null fixed stat column

For implementation clarity, internal code may name this metric `contributing_source_count`, but the API response remains `source_count` for backward compatibility.

### 7.3 VORP replacement-level handling for `UTIL` and `BN`

Replacement-level thresholds use only positional starter slots: `C`, `LW`, `RW`, `D`, `G`.

- Exclude `UTIL` and `BN` from replacement-level math in v1.0
- Continue using NHL canonical `players.position` for the replacement group
- Phase 4 draft-session logic handles dynamic roster need (including UTIL/bench state) separately from static VORP

This keeps VORP stable and prevents artificial inflation from non-positional slots.

### 7.4 Redis invalidation method

`invalidate_rankings(season)` must use cursor-based `SCAN` with batched deletes, not `KEYS`.

- Pattern: `rankings:{season}:*`
- Delete in batches (recommended batch size: 100 keys)
- Continue until cursor returns to 0

Reason: `KEYS` can block Redis on large keyspaces and is not production-safe.

### 7.5 Optional baseline source behavior (NHL.com / MoneyPuck)

If a user explicitly enables NHL.com or MoneyPuck as a baseline projection source, values are derived from prior-season actuals with no adjustment model.

- Source label in UI/export: `Prior Season Actuals (Unadjusted)`
- Transform rule: map available `player_stats` columns from season `S-1` into `player_projections` for season `S`
- No aging, regression, pace, or deployment adjustment in v1.0

This baseline is intentionally naive and should be down-weighted relative to true projection providers.

### 7.6 Explicit RLS and access policy requirements

RLS policies must be explicit for multi-tenant safety:

- `league_profiles`
  - `SELECT/INSERT/UPDATE/DELETE`: `user_id = auth.uid()`
- `sources`
  - `SELECT`: `user_id IS NULL OR user_id = auth.uid()`
  - `INSERT/UPDATE/DELETE`: `user_id = auth.uid()` for user-owned rows only
  - System rows (`user_id IS NULL`) are read-only from user context
- `player_projections`
  - Read access only through rows whose `source_id` maps to a source visible under the `sources` policy above
  - Direct client writes are disallowed; writes occur through trusted backend ingestion paths

These policies are required in addition to API-layer checks.
