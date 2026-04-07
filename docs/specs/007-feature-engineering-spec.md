# PuckLogic: Feature Engineering Specification

## Trends Engine — ML Model (XGBoost/LightGBM)

**Version 1.0 · March 2026**
**Reference:** `docs/research/001-nhl-advanced-stats-research.md` for full methodology and source citations

-----

## How to Use This Document

This spec feeds directly into Claude Code sessions. When starting Phase 3 (ML Trends Engine), open a session with:

> *"Build the feature engineering pipeline per `docs/specs/007-feature-engineering-spec.md` using MoneyPuck CSVs and Natural Stat Trick as primary sources."*

-----

## Tiered Feature Reference

### Tier 1 — Core Features (Always Include)

|Feature          |Description                                  |Notes                                                                        |Primary Source                 |
|-----------------|---------------------------------------------|-----------------------------------------------------------------------------|-------------------------------|
|`icf_per60`      |Individual Corsi For per 60 min              |Best shot generation metric; do NOT include alongside `isf_per60` (collinear)|Natural Stat Trick             |
|`ixg_per60`      |Individual expected goals per 60 min         |Shot quality; pair with `icf_per60` — one volume, one quality                |MoneyPuck, NST                 |
|`g_minus_ixg`    |Goals minus individual xG (current season)   |**Primary breakout/regression signal.** Negative = buy; positive = sell      |MoneyPuck, NST                 |
|`xgf_pct_5v5`    |On-ice xGF% at 5v5 (score-adjusted)          |Best single play-driving metric; R² ≈ 0.48 vs. GF%                           |MoneyPuck, NST, Evolving Hockey|
|`cf_pct_adj`     |Score-and-venue-adjusted Corsi For %         |Highest repeatability; fastest stabilization (~10 games)                     |NST, Hockey Reference          |
|`scf_per60`      |Individual scoring chances per 60 min        |Most predictive metric for future goals; underutilized in industry           |Natural Stat Trick             |
|`scf_pct`        |On-ice scoring chance %                      |Outperforms both CF% and xG for offensive prediction (Knodell 2025)          |Natural Stat Trick             |
|`p1_per60`       |Primary points (G + A1) per 60 min           |Best traditional-stat projection input; strips near-random A2 noise          |NST, Evolving Hockey           |
|`toi_ev_per_game`|Even-strength TOI per game                   |Core deployment feature; rate × TOI = counting stat projection               |All sites                      |
|`toi_pp_per_game`|Power play TOI per game                      |Essential alongside PP unit designation                                      |All sites                      |
|`toi_sh_per_game`|Short-handed TOI per game                    |Deployment context; also fantasy category in some leagues                    |All sites                      |
|`pp_unit`        |PP unit designation (1, 2, or 0)             |3.2× higher breakout rate for PP1 D; biggest marginal value driver           |DailyFaceoff, manual           |
|`pdo`            |On-ice SH% + on-ice SV% (normalized to 1.000)|>1.02 or <0.98 = strong unsustainable luck flag                              |NST, Hockey Reference          |
|`sh_pct_delta`   |Current season SH% minus career SH%          |**Primary regression detection signal.** >4% = likely regression             |Hockey Reference (career)      |
|`age`            |Player age at season start                   |Core aging curve feature; interacts with all rate stats                      |Hockey Reference               |

-----

### Tier 2 — Supplementary Features (Include with Caveats)

|Feature          |Description                                 |Caveat                                                              |Source                 |
|-----------------|--------------------------------------------|--------------------------------------------------------------------|-----------------------|
|`cf_pct_rel`     |CF% relative to team when player is off ice |Drop if using RAPM (collinear)                                      |NST                    |
|`gar` or `xgar`  |Goals Above Replacement (observed/expected) |Use `gar` for forwards, `xgar` for defensemen                       |Evolving Hockey ($5/mo)|
|`xga_per60`      |Expected goals against per 60 min (on-ice)  |Defensive eval is noisy; use Evolving Hockey EVD if available       |NST, MoneyPuck         |
|`g_per60`        |Goals per 60 min                            |Moderate stability; P1/60 subsumes most of this signal              |NST                    |
|`a1_per60`       |Primary assists per 60 min                  |Include separately from G/60 for position-specific models           |NST                    |
|`ppp_per60`      |Power play points per 60 PP min             |Always pair with `toi_pp_per_game` and `pp_unit`                    |NST                    |
|`toi_rank`       |Percentile rank of TOI within position group|Captures top-6 vs. bottom-6 without hard thresholds                 |Compute from NST       |
|`qot_score`      |Quality of teammates score                  |~3× more important than QoC; use Evolving Hockey or WoodMoney       |Evolving Hockey        |
|`nhl_experience` |Years played in NHL                         |Interacts with age for aging curve calibration                      |Hockey Reference       |
|`position_code`  |F/D/W/C categorical                         |Position-specific aging and deployment patterns differ significantly|All sites              |
|`fo_pct`         |Faceoff win %                               |Only include for leagues scoring faceoffs                           |NHL.com, HR            |
|`zone_entry_rate`|Controlled entry % (carry-ins vs. dump-ins) |Highly predictive but limited availability (Patreon)                |All Three Zones        |

-----

### Tier 3 — Situational Features (Use Carefully)

|Feature               |Description                                 |Issue                                                        |Source               |
|----------------------|--------------------------------------------|-------------------------------------------------------------|---------------------|
|`speed_bursts_22`     |Count of speed bursts ≥22 mph per game      |Only 5 seasons of data; individual predictiveness unvalidated|NHL EDGE             |
|`top_speed`           |Max skating speed recorded                  |Best aging indicator in EDGE data; supplement only           |NHL EDGE             |
|`ozs_pct`             |Offensive zone start %                      |Only captures ~42% of shifts; modest adjustment value        |NST                  |
|`hits_per60`          |Arena-adjusted hits per 60 min              |Category leagues only; negative possession correlation       |NST (home/away split)|
|`blocks_per60`        |Blocked shots per 60 min                    |Category leagues only; contextual (team system)              |NST                  |
|`pim_per60`           |Penalty minutes per 60 min                  |Format-dependent; reflects identity not performance change   |All sites            |
|`oi_sh_pct`           |On-ice shooting % while on ice              |Regression signal only; 96.4% don't repeat >11%              |NST                  |
|`contract_year_flag`  |Binary: is player in final year of contract?|Weak signal; statistically insignificant in aggregate        |Manual / PuckPedia   |
|`post_extension_flag` |Binary: signed new contract this season?    |Negative signal; production declines in 73% of cases         |Manual / PuckPedia   |
|`elc_flag`            |Binary: player on entry-level contract      |Combined with TOI: 14+ ES min = 43% breakout probability     |Manual               |
|`coaching_change_flag`|Binary: new head coach this season          |Material impact (±1 WAR) but requires manual maintenance     |Manual               |
|`trade_flag`          |Binary: player traded in/out in offseason   |Context change; can be positive or negative                  |Manual               |

-----

### Tier 4 — Exclude (Do Not Include)

|Feature                             |Reason                                                                                |
|------------------------------------|--------------------------------------------------------------------------------------|
|`plus_minus`                        |Consensus worst stat in hockey; confounded by goaltending, PP exclusion, score effects|
|`takeaways` / `giveaways`           |Arena scorer bias of 200–800%+; no official NHL definition                            |
|`ff_pct` (Fenwick)                  |Collinear with CF%; signal fully captured by xG                                       |
|`hdcf_pct` (standalone)             |Lowest repeatability of all possession metrics; loses information vs. SCF% or xG      |
|`hd_shot_rates`                     |Redundant with xG; danger decomposition already captured                              |
|`oi_sv_pct`                         |Near-zero player control; goaltender-driven                                           |
|`shp_per60`                         |Sample too small for individual prediction                                            |
|`qoc_score`                         |Washes out at aggregate level; RAPM makes it redundant                                |
|`secondary_assists_pct` (standalone)|Near-zero year-over-year correlation; use only as regression flag component           |
|`ga_per60`                          |Replaced by xGA/60; confounded by goaltending                                         |

-----

## Breakout Candidate Detection Rules

Flag a player as a **breakout candidate** when **3 or more** of the following are true:

```python
breakout_signals = {
    "g_below_ixg":        player["g_per60"] < player["ixg_per60"] * 0.85,      # Shooting below xG
    "sh_pct_below_career": player["sh_pct_delta"] < -0.03,                       # SH% depressed vs. career
    "rising_shot_gen":    player["icf_per60_delta"] > 0.5,                       # Shot volume trending up
    "pp_promotion":       player["pp_unit_change"] == "PP2→PP1",                 # PP role upgrade
    "prime_age_window":   20 <= player["age"] <= 25,                             # Development age window
    "strong_underlying":  player["xgf_pct_5v5"] > 52.0,                         # Driving play
    "bad_luck_pdo":       player["pdo"] < 0.975,                                 # Below-average PDO
    "elc_deployed":       player["elc_flag"] and player["toi_ev_per_game"] >= 14  # Rookie with real role
}
```

-----

## Regression Risk Detection Rules

Flag a player as a **regression risk** when **3 or more** of the following are true:

```python
regression_signals = {
    "g_above_ixg":         player["g_per60"] > player["ixg_per60"] * 1.20,      # Shooting above xG
    "sh_pct_above_career": player["sh_pct_delta"] > 0.04,                        # SH% inflated vs. career
    "high_pdo":            player["pdo"] > 1.025,                                # Unsustainably lucky PDO
    "high_oi_sh_pct":      player["oi_sh_pct"] > 0.11,                          # 96.4% don't repeat this
    "high_secondary_pct":  False,  # D8: a1 (primary assists) counting stat not in schema; always False
    "age_declining":       player["age"] > 30 and player["position"] in {"C", "LW", "RW"},  # NHL.com canonical positions
    "declining_shot_gen":  player["icf_per60_delta"] < -0.5,                    # Shot volume dropping
}
```

> **Elite finisher exemption:** ~~Do not apply `g_above_ixg` flag to confirmed elite shooters with 3+ seasons of above-expected finishing.~~ **D5: No whitelist — XGBoost learns from data. `g_above_ixg` fires for all players.**

-----

## Projection Pipeline (Step-by-Step)

```
1. COMPUTE RATE STATS
   - Use 3-year weighted window: current season × 0.5, Y-1 × 0.3, Y-2 × 0.2
   - Minimum sample threshold: 300 minutes ES TOI per season
   - Rate = (weighted sum of events) / (weighted sum of TOI) × 60

2. REGRESS SHOOTING PERCENTAGE
   - Regress current SH% toward career mean
   - Regression weight by sample size: smaller sample = stronger pull to career mean
   - Example: 50-shot season → 70% regression to career mean; 250-shot season → 25% regression

3. PROJECT TIME ON ICE
   - Use 3-year weighted average (same weights as above)
   - Apply aging curve adjustment by age/position
   - Apply context flags: PP role change ±15–30%, coaching change ±10%, trade ±5–15%

4. APPLY AGING CURVE ADJUSTMENT
   - Forwards: peak at 24–28; apply decline curve after 28
   - Defensemen: peak at 28–29; gentler slope to 34
   - Multiply rate stats by age adjustment factor before projection

5. MULTIPLY: projected counting stat = adjusted_rate × projected_TOI

6. APPLY CONTEXT FLAGS
   - PP promotion: increase PPP projection by 30–50% for PP1 recipients
   - ELC + deployment: if rookie TOI ≥14 ES min/game, apply 43% breakout probability uplift
   - Injury history: multiply by projected games played / 82

7. RUN BREAKOUT/REGRESSION CHECKS
   - Apply detection rules above
   - Output confidence tier: HIGH (4+ signals), MEDIUM (3 signals), LOW (2 signals)
   - Add to player_trends table: breakout_score, regression_risk, confidence, updated_at

8. SHAP EXPLAINABILITY
   - After XGBoost/LightGBM training, compute SHAP values per prediction
   - Surface top 3 SHAP contributors per player in UI ("Why is this player flagged?")
   - This is the primary user-facing explainability output
```

-----

## Data Source Pipeline

```
PRIMARY DATA SOURCES
├── MoneyPuck (moneypuck.com/data.htm)
│   ├── shots.csv          → ixG, shot-level xG, danger zones, flurry-adjusted
│   ├── skaters.csv        → player-level aggregates, ixG/60, CF%, SCF%
│   └── teams.csv          → team-level context
├── Natural Stat Trick (naturalstattrick.com)
│   ├── /playerteams       → SCF%, HDCF%, xG splits, on/off metrics
│   ├── /playerlines       → line context, PP/SH splits
│   └── Scraping method: BeautifulSoup + URL params
├── Hockey Reference (hockey-reference.com)
│   ├── /players/          → career SH%, traditional stats, age, experience
│   └── Export method: "Get table as CSV" button
└── NHL EDGE (nhl.com/nhl-edge)
    ├── Speed burst counts, top speed, zone time
    └── Access: nhl-api-py (Python) or nhlscraper (R)

SUPPLEMENTARY (PAID)
└── Evolving Hockey (evolving-hockey.com) — $5/month
    ├── GAR / xGAR / WAR   → use as comprehensive value benchmark
    ├── RAPM               → replaces CF% Rel and QoT/QoC
    └── EVD                → best individual defensive metric available

CONTEXT DATA (MANUAL / SCRAPED)
├── DailyFaceoff.com       → PP unit designation, line combos (pre-season critical)
├── LeftWingLock           → depth chart, projected line deployments
└── PuckPedia.com          → contract status, ELC flag, contract year
```

-----

## Database Target Schema

Maps to `player_trends` and `player_stats` tables from architecture doc:

```sql
-- player_stats (raw inputs — from ingestion pipeline)
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS icf_per60 FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS ixg_per60 FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS xgf_pct_5v5 FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS cf_pct_adj FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS scf_per60 FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS scf_pct FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS p1_per60 FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS pdo FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS sh_pct FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS toi_ev FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS toi_pp FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS toi_sh FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS pp_unit SMALLINT;      -- 0, 1, or 2
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS gar FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS xgar FLOAT;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS speed_bursts_22 FLOAT;  -- EDGE
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS elc_flag BOOLEAN;
ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS contract_year_flag BOOLEAN;

-- player_trends (ML outputs — from nightly Celery job)
-- Already defined in architecture doc:
-- breakout_score FLOAT, regression_risk FLOAT, confidence FLOAT, updated_at TIMESTAMP
-- Add these:
ALTER TABLE player_trends ADD COLUMN IF NOT EXISTS breakout_signals JSONB;  -- which signals triggered
ALTER TABLE player_trends ADD COLUMN IF NOT EXISTS regression_signals JSONB;
ALTER TABLE player_trends ADD COLUMN IF NOT EXISTS shap_top3 JSONB;         -- top SHAP contributors
ALTER TABLE player_trends ADD COLUMN IF NOT EXISTS projection_pts FLOAT;    -- projected fantasy pts
ALTER TABLE player_trends ADD COLUMN IF NOT EXISTS projection_tier VARCHAR; -- 'HIGH'/'MEDIUM'/'LOW'
```

-----

## Multicollinearity Warnings

**Do NOT include these together in the same model:**

|Group                                  |Problem                         |Resolution                                            |
|---------------------------------------|--------------------------------|------------------------------------------------------|
|`icf_per60` + `isf_per60` + `ixg_per60`|All highly correlated           |Use `icf_per60` (volume) + `ixg_per60` (quality) only |
|`cf_pct_adj` + `cf_pct_rel` + RAPM     |Measuring same thing differently|Use RAPM if available; else `cf_pct_rel`; drop raw CF%|
|`p1_per60` + `g_per60` + `a1_per60`    |P1/60 = G + A1                  |Use `p1_per60`; add `g_per60` only if model benefits  |
|`pdo` + `oi_sh_pct` + `oi_sv_pct`      |PDO = sum of these              |Use `pdo` + `sh_pct_delta`; drop individual components|
|`gar` + `xgar` + WAR                   |Different forms of same metric  |Pick one per position group                           |

-----

## Training Data Requirements

```
Minimum: 10 seasons of historical NHL data (2008–2018 training, 2019–2025 validation)
Recommended sources:
  - Hockey Reference: season-level stats (free scraping, full history)
  - MoneyPuck: xG and shot-level data from 2007–08 onward (CSV download)
  - Natural Stat Trick: Corsi/xG/SCF splits from 2007–08 onward (scraping)

Label construction:
  - "Breakout":   player scores ≥20% more fantasy pts than trailing 2-season average
  - "Regression": player scores ≥20% fewer fantasy pts than trailing 2-season average
  - "Neutral":    all others

Train: seasons 2008–2022
Validate: seasons 2023–2025
Minimum TOI threshold: 500 ES minutes per season (filter noise from depth players)
```

-----

## Scope: Skaters Only (Phase 3c)

The feature engineering pipeline in Phase 3c is **skaters only**. Goalies are not filtered out, but
the skater-specific signals (icf_per60, ixg_per60, xgf_pct_5v5, etc.) are meaningless for goalies.

**Goalie projections are a future requirement** (Notion backlog: "Goalie projections statistical
model — design and implement feature engineering"). A separate model with goalie-specific features
is required:

| Feature (proposed) | Description | Source |
|--------------------|-------------|--------|
| `sv_pct`           | Save percentage | NHL.com, Hockey Reference |
| `gaa`              | Goals-against average | NHL.com, Hockey Reference |
| `high_danger_sv_pct` | High-danger save % | MoneyPuck, NST |
| `gsax`             | Goals saved above expected | MoneyPuck |
| `start_pct`        | % of team starts | NST |
| `qstart_pct`       | Quality start % | Hockey Reference |

Until this is implemented, goalie rows pass through `build_feature_matrix` using skater logic and
produce undefined/misleading results. Do not surface goalie trend scores to users until the goalie
model is complete.

-----

*Full methodology and source citations: `docs/research/001-nhl-advanced-stats-research.md`*
*Architecture context: `pucklogic_architecture.docx`*
