# PuckLogic: NHL Advanced Stats Research

## Fantasy Hockey ML Projection Models — Full Reference

**Version 1.0 · March 2026 · Skaters Only**

> The most predictive features for a fantasy hockey ML model are not the ones most fantasy managers watch. Individual shot generation rates (iSF/60, iCF/60), primary points per 60, power play deployment, and the gap between expected and actual goals form the statistical backbone of breakout and regression identification. Traditional counting stats like goals and assists are lagging indicators — noisy outputs of underlying processes that advanced metrics capture far earlier and more reliably.

-----

## Data Infrastructure Summary

The modern hockey analytics ecosystem offers extraordinary depth for free:

- **MoneyPuck** — downloadable shot-level CSVs, 124 attributes per shot, 2007–08 to present
- **Natural Stat Trick** — scoring chances, xG, Corsi/Fenwick, on/off splits, PP/SH splits; 2007–08 to present
- **Hockey Reference** — traditional stats, PDO, career data, CSV export; 1917–18 to present
- **NHL EDGE** — skating speed, distance, shot speed, zone time; 2021–22 to present (unofficial API)
- **Evolving Hockey** — GAR/xGAR/WAR, RAPM; **$5/month — essential**
- **The Athletic (Dom Luszczyszyn)** — GSVA projections; ~$8/month

-----

## Basic & Traditional Stats

### Goals (G)

**Definition:** Pucks put in the net. Year-over-year R² ≈ 0.16 at even strength — moderate-low stability because goals depend heavily on shooting percentage, which is largely luck-driven in single seasons. Shot volume is the repeatable underlying driver; conversion rate fluctuates wildly.

**Verdict: INCLUDE WITH CAUTION.** Use as a target variable, not a primary input feature. Decompose into shot volume × shooting percentage and model each separately.

**Sources:** All sites (Hockey Reference, Natural Stat Trick, MoneyPuck, NHL.com).

-----

### Assists — Primary (A1) vs. Secondary (A2)

**Definition:** A1 = the last pass before the goal; A2 = the pass before that. A1 year-over-year R² ≈ 0.16 (identical to goals). A2 year-over-year correlation is near zero — "only a small step above random." Total assists (A1+A2) are marginally more predictive than A1 alone (R² ≈ 0.19 for total points vs. 0.16 for primary points). For defensemen specifically, A2 correlates more strongly with Corsi Rel than for forwards because point shots frequently generate secondary assists via deflections.

**Verdict: INCLUDE A1; USE A2 WITH CAUTION.** Weight primary assists ~2× secondary. Recommended scheme: G = 1.0, A1 ≈ 0.67, A2 ≈ 0.33. **Primary points (P1 = G + A1) is the single best traditional counting stat for projection.**

**Sources:** Natural Stat Trick and Evolving Hockey for cleanest breakdowns.

-----

### Points (Pts)

**Definition:** G + A. R² ≈ 0.19 year-over-year — the strongest of all traditional counting stats. Points benefit from aggregating across goals and both assist types, which smooths noise.

**Verdict: INCLUDE** as a baseline feature. Points per 60 and primary points per 60 are strictly better model inputs than raw counting totals.

**Sources:** All sites.

-----

### Plus/Minus (+/−)

**Definition:** +1 when on ice for an even-strength or shorthanded goal for; −1 for a goal against. Excludes power play goals for but includes PP goals against.

**Why it fails:** Goals are rare events with high randomness. The PP exclusion rule systematically skews results. Heavily confounded by goaltending quality, teammate quality, and score effects. Year-over-year standard deviation of ES goal differential is only ~9 goals per season — small random swings dominate. Per Hockey Graphs, plus/minus is "the worst statistic in hockey and should be abolished."

**Verdict: EXCLUDE.** Replace entirely with Corsi, xG, or WAR-based metrics.

**Sources:** Hockey Reference, NHL.com (but don't use).

-----

### Penalty Minutes (PIM)

**Definition:** Minutes spent in the penalty box. Moderate repeatability — physical players consistently accumulate PIM, and penalty tendencies are moderately stable skills. Fantasy relevance is format-dependent: positive in traditional rotisserie (more = better), negative in points leagues (~−1.7 pts per PIM).

**Verdict: INCLUDE for multi-category formats; EXCLUDE for points-only leagues.** PIM reflects player identity/role rather than performance changes.

**Sources:** All sites.

-----

### Power Play Goals (PPG) and Power Play Points (PPP)

**Definition:** Goals and points scored on the power play. Stability is moderate but heavily deployment-dependent — whether a player sits on PP1 is arguably more important than underlying skill. Defensemen on PP1 have a **3.2× higher breakout rate** than PP2 players.

**Verdict: INCLUDE, but always paired with PP TOI and PP unit designation.** PPP without deployment context is misleading.

**Sources:** All sites; Natural Stat Trick and Evolving Hockey for PP splits.

-----

### Short-Handed Points (SHP)

**Definition:** Points scored while shorthanded. Extremely rare events (~5–7% of all NHL goals are shorthanded). League leaders change dramatically year-over-year.

**Verdict: EXCLUDE.** Sample sizes far too small for individual prediction.

**Sources:** Hockey Reference, NHL.com.

-----

### Shots on Goal (SOG)

**Definition:** Shot attempts that reach the goaltender or go in. One of the most stable individual offensive stats in hockey. Shots have much higher autocorrelation than goals because they capture shot generation ability without the high-variance conversion component.

**Verdict: INCLUDE (Tier 1).** Individual shots per 60 (iSF/60) is among the most valuable ML inputs — a leading indicator of goal production with high year-over-year stability.

**Sources:** All sites.

-----

### Shooting Percentage (SH%)

**Definition:** Goals ÷ shots on goal. Low single-season repeatability. CBS Sports found top-50 SH% leaders averaged a >4% drop the following season, with only ~20% returning to the top 50. There is a small skill component for elite snipers (13–17% career SH%) vs. fourth-liners (~7–9%), but single-season SH% is heavily luck-driven.

**Verdict: USE WITH CAUTION.** Do not use raw single-season SH% as a feature. Use the **delta between current-season SH% and career SH% (3+ seasons)** as a regression signal — one of the most powerful features available.

**Sources:** All sites; Hockey Reference for career SH% data.

-----

### Time on Ice (TOI) — Total, PP, EV, SH

**Definition:** Minutes played per game by game state. High year-over-year stability. PP TOI is the single strongest predictor of PPP production. Key benchmarks: top-line forwards 14–18 min EV; top-pair D 18–22 min EV.

**Verdict: INCLUDE (Tier 1) — all subtypes.** TOI decomposition (EV, PP, SH) is essential. The projection formula is: **rate stat × projected TOI = counting stat projection.**

**Sources:** All sites; Natural Stat Trick for granular splits.

-----

### Takeaways (TK) and Giveaways (GV)

**Definition:** Plays where a player gains/loses possession. Massive arena scorer bias — in 2006–07, Edmonton recorded 923 home giveaways while Chicago recorded 99 (832% difference). The NHL has **no official written definition**. Ryan O'Reilly led the league in takeaways in Colorado; after a trade to Buffalo, he could barely crack the top 40.

**Verdict: EXCLUDE.** Even road-only splits are suspect. No reliable signal.

**Sources:** NHL.com, Hockey Reference (data quality is poor at all sources).

-----

### Hits

**Definition:** Physical contact initiated by a player. Significant arena bias — Pittsburgh had +16.6 more hits per home game than away; Buffalo had −11.6. Moderate repeatability for physical players, but reflects player identity more than performance.

**Verdict: INCLUDE WITH CAUTION for multi-category leagues only.** Use arena-adjusted or road-only data.

**Sources:** All sites; Natural Stat Trick offers home/away filtering.

-----

### Blocked Shots

**Definition:** Shots blocked by a skater. Moderate repeatability, partly a function of team system and defensive zone time. High blocked shots can indicate good defense OR poor possession — Kris Russell led the league in blocks while having terrible Corsi numbers because his team never had the puck.

**Verdict: INCLUDE WITH CAUTION for category leagues.** Requires context — combine with CF% or xG data.

**Sources:** All sites.

-----

## Possession & Shot Metrics

### Corsi For % (CF%)

**Definition:** CF% = CF / (CF + CA), where Corsi = all shot attempts (SOG + missed shots + blocked shots). Score-and-venue-adjusted CF% is the standard. HockeyViz found it was the most repeatable and predictive Corsi variant. Most players fall between 40–60%; elite play-drivers at 55%+.

**Predictive value:** R² of CF% to GF% (same season, team level) ≈ 0.27. Highest year-over-year repeatability among all possession metrics. Reaches near-peak predictive power by ~10 games into a season.

**Verdict: INCLUDE (Tier 1).** Use score-and-venue-adjusted CF% at 5v5. Workhorse possession metric — large sample size, fast stabilization, excellent repeatability.

**Sources:** Natural Stat Trick, MoneyPuck, Hockey Reference, Evolving Hockey.

-----

### Fenwick For % (FF%)

**Definition:** Like Corsi but excludes blocked shots (SOG + missed shots only). FF% correlates slightly more with winning than CF% over full seasons (R² ≈ 0.30 vs. 0.22), but CF% has larger sample size and stabilizes faster.

**Verdict: EXCLUDE (collinear with CF%).** Fenwick's signal is captured through xG. Including both creates multicollinearity.

**Sources:** Natural Stat Trick, MoneyPuck, Hockey Reference.

-----

### Relative Corsi (CF% Rel) and Relative Fenwick

**Definition:** Player's on-ice CF% minus team's CF% when player is off ice. Attempts to isolate individual contribution from team quality. A player on a bad team might have 47% CF% but +3% CF% Rel.

**Limitations:** Still affected by linemate quality and deployment. RAPM from Evolving Hockey does better job of true isolation.

**Verdict: INCLUDE (Tier 2).** Better than raw CF% for individual evaluation. If RAPM is available, use RAPM and drop CF% Rel to avoid redundancy.

**Sources:** Natural Stat Trick, Hockey Reference, Evolving Hockey (RAPM).

-----

### Zone Start % (OZS%, DZS%)

**Definition:** OZS% = offensive zone faceoffs / (OZ + DZ faceoffs). Players with high OZS% tend to have inflated CF%. However, **>58% of all shifts begin "on the fly"** (not after a stoppage), diluting the zone start effect considerably. Each net offensive zone start is worth only ~0.8 extra shot attempts.

**Verdict: USE WITH CAUTION (Tier 3).** Include as a context feature to adjust possession metrics, but do not overweight. Most modern analysts consider zone starts secondary compared to score adjustment.

**Sources:** Natural Stat Trick, Hockey Reference, Evolving Hockey.

-----

### Zone Entry Differential

**Definition:** Controlled entries (carry-ins) vs. dump-ins at the offensive blue line. Controlled entries generate ~0.66 unblocked shot attempts vs. ~0.29 for dump-ins (Corey Sznajder, All Three Zones). Neutral zone play is the primary determinant of shot differential.

**Verdict: INCLUDE if available (Tier 2).** Not widely available publicly — Sznajder's tracking is Patreon-funded; NHL EDGE does not yet publish zone entries/exits.

**Sources:** All Three Zones (allthreezones.com, Patreon). **Not on NHL EDGE.**

-----

### Scoring Chances For % (SCF%)

**Definition:** Shot attempts weighted by danger zone location. Natural Stat Trick: low (1 pt), medium (2 pt), high-danger (3 pt) zones, with bonuses for rebounds (+1) and rush shots (+1). A scoring chance = any shot scoring 2+.

**The sleeper hit of hockey analytics:** Per Puck Over the Glass (December 2025), **scoring chances are the most predictive underlying metric for future 5v5 goal differential**, outperforming both Corsi and xG for offensive prediction. For defense, Corsi remains better. SCF% has slightly less repeatability than CF% but significantly more predictive power — yet remains "largely ignored" in practice.

**Verdict: INCLUDE (Tier 1).** Underutilized and underrated. SCF% and iSCF/60 should be core features in PuckLogic.

**Sources:** Natural Stat Trick (primary), Hockey Reference, Evolving Hockey.

-----

## Expected Goals Metrics

### xG Model Comparison

|Model             |Algorithm                      |Key Innovation                              |Calibration                     |
|------------------|-------------------------------|--------------------------------------------|--------------------------------|
|MoneyPuck         |Gradient boosting, 15 variables|Flurry adjustment (discounts rapid rebounds)|Slightly underestimates         |
|Evolving Hockey   |XGBoost                        |Shooter-adjusted and non-adjusted versions  |Overestimates by ~6%            |
|Natural Stat Trick|Zone-based logistic regression |Rush/rebound bonuses                        |Best calibrated (0.7% overshoot)|

**Predictive value:** R² of xGF% to GF% (same-season, team level) ≈ 0.48 — substantially better than CF% (≈ 0.27). MoneyPuck's shot-level CSV data (124 attributes per shot, free download) is ideal for custom xG model training.

-----

### xGF% (Expected Goals For %, On-Ice, 5v5)

**Definition:** Expected goals generated by a player's team while they're on ice, as a percentage of total expected goals. Best single play-driving metric available.

**Verdict: INCLUDE (Tier 1).**

**Sources:** MoneyPuck, Natural Stat Trick, Evolving Hockey.

-----

### Individual xG (ixG) and xG/60

**Definition:** ixG = sum of xG values from a player's own shot attempts only. Measures individual shot quality generation independent of teammates.

**Key application:** Comparing ixG to actual goals reveals finishing skill vs. luck. **G >> ixG = overperforming (regression candidate); G << ixG = underperforming (breakout candidate).** This gap is the single most actionable metric for breakout/regression identification.

**Verdict: INCLUDE (Tier 1).** ixG and the G-minus-ixG delta are essential features.

**Sources:** Natural Stat Trick, MoneyPuck.

-----

### Goals Above Expected (G − xG)

**Mostly luck in small samples, partially skill over multi-year horizons.** An arxiv paper (2024) simulated that even a highly skilled finisher taking 100 shots/season has only ~70% probability of outperforming cumulative xG in 4+ of 5 seasons. JFresh found only **3.6% of players with >11% on-ice SH% repeated it the next year.**

**Verdict: INCLUDE as a regression/breakout signal, not a skill feature.** Treat large positive G−xG as a regression flag and large negative G−xG as a buy-low signal — except for confirmed elite finishers (Matthews, Draisaitl, Ovechkin) with 3+ years of above-expected finishing.

**Sources:** Natural Stat Trick, MoneyPuck.

-----

### High-Danger Chances (HDCF%, HDSC%)

**Definition:** MoneyPuck defines high-danger as shots with ≥20% goal probability (~5% of all shots, ~33% of goals). HDCF% has the **lowest repeatability** of the major possession metrics — lower than CF%, SCF%, and xGF%. Double-counting HD chances actually lessened predictive power vs. using all scoring chances (Knodell 2025).

**Verdict: EXCLUDE as a standalone feature.** HD information is already captured (better) by xG and SCF%. Redundant and lower signal.

**Sources:** Natural Stat Trick, MoneyPuck.

-----

### xGA and xGA/60 (Expected Goals Against)

**Definition:** Quality of scoring chances allowed while a player is on ice. For predicting future goals against, **Corsi performs comparably to or better than xG** (Knodell 2025). Goaltending talent dominates defensive outcomes.

**Verdict: INCLUDE WITH CAUTION (Tier 2).** xGA/60 is the best available defensive metric for skaters, but expect low model lift from defensive features. Evolving Hockey's RAPM-based EVD is better if available.

**Sources:** Natural Stat Trick, MoneyPuck, Evolving Hockey.

-----

### Medium-Danger and Low-Danger Shot Rates

**Verdict: EXCLUDE.** Danger zone decomposition is already captured by xG models. Including raw danger-zone rates alongside xG is redundant.

-----

## Individual Skill & Efficiency Metrics

### Rate Stats: G/60, A1/60, P/60, P1/60

**Rate stats are strictly superior to counting stats for projection modeling.** They separate talent (rate) from deployment (TOI), enabling: *projected counting stat = rate × projected TOI*.

**Primary Points per 60 (P1/60)** is the best traditional-stat projection input — it strips near-random secondary assists while aggregating the most repeatable offensive signals. Ryan Stimson's work at Hockey Graphs showed shot assists stabilize after just 8 games (r = 0.261), while A1/60 takes 41 games to reach similar stability.

**Verdict: INCLUDE P1/60 (Tier 1), G/60 and A1/60 (Tier 2).**

**Sources:** Natural Stat Trick, Evolving Hockey.

-----

### Individual Shots per 60 (iSF/60) and Individual Corsi per 60 (iCF/60)

Among the most stable individual offensive metrics in hockey. Shot generation is a genuine repeatable skill. Hockey Graphs confirmed shots have "much higher autocorrelation than goals."

**Multicollinearity warning:** iSF/60, iCF/60, iFF/60, and ixG/60 are all highly correlated. "We wouldn't want to include each of iSF, iCF, iFF, and ixG in the same regression." — Hockey Graphs. **Pick one shot-volume metric (iCF/60) and one shot-quality metric (ixG/60).**

**Verdict: INCLUDE ONE (Tier 1).** Use iCF/60 for broader shot generation capture. Do not include both iSF/60 and iCF/60.

**Sources:** Natural Stat Trick, MoneyPuck.

-----

### PDO (On-Ice SH% + On-Ice SV%)

**Definition:** Sum of on-ice shooting percentage and save percentage — centers around 100. Both components have weak year-over-year repeatability. JFresh's 10-year analysis showed PDO is "almost completely random" from Year 1 to Year 2.

**Verdict: INCLUDE (Tier 1) as a regression flag.** PDO >102 or <98 is a strong signal of unsustainable luck. Flag players with extreme PDO for regression adjustment.

**Sources:** Natural Stat Trick, Hockey Reference.

-----

### On-Ice SH% and On-Ice SV%

**On-ice SH%:** Of 138 skater-seasons with >11% oiSH%, only **5 (3.6%) repeated** above 11% the next year.

**On-ice SV%:** Largely driven by goaltender quality. "There doesn't seem to be much consistency across players" — Grantland.

**Verdict: On-ice SH% — USE WITH CAUTION (Tier 3) as regression signal. On-ice SV% — EXCLUDE.**

**Sources:** Natural Stat Trick, Hockey Reference.

-----

## Defensive & Two-Way Metrics

> Defensive evaluation remains hockey analytics' greatest challenge. Offensive metrics predict future results with R² ≈ 0.47; defensive zone efficiency has R² ≈ 0.09. Goaltending talent dominates defensive outcomes for skaters.

### Goals Against per 60 (GA/60)

**Verdict: EXCLUDE.** Poor at isolating individual defensive impact. Replaced by xGA/60 and RAPM-based metrics.

-----

### xGA/60 On Ice

Better than GA/60 as it removes goaltending variance. Evolving Hockey's **RAPM-based EVD (Even-Strength Defense)** component is the best publicly available individual defensive metric.

**Verdict: INCLUDE WITH CAUTION (Tier 2).** Use Evolving Hockey EVD if accessible; otherwise use on-ice xGA/60 with noise discounting.

-----

### Hits/60 and Blocked Shots/60

Arena bias affects both. Slight **negative** correlation between hitting and possession (hitting often means not having the puck).

**Verdict: INCLUDE for category league formats only (Tier 3).** Not useful for projection accuracy.

-----

### GAR / GSVA / WAR

- **GAR** (Goals Above Replacement, Evolving Hockey): R package + web UI, $5/month. Best public all-in-one player value metric.
- **GSVA** (Dom Luszczyszyn, The Athletic): 3-year weighted composite. Use observed GAR for forwards; expected (xGAR) for defensemen.
- **WAR** (Evolving Hockey): Same underlying data, expressed in wins.

**Verdict: INCLUDE (Tier 2).** Use GAR as a comprehensive value benchmark, especially for defensive evaluation where individual metrics fail.

-----

## Deployment & Context Metrics

### PP1 vs. PP2 Designation

**The single biggest driver of marginal fantasy value differentiation.** Defensemen on PP1 have a 3.2× higher breakout rate. Some teams (Edmonton) give PP1 nearly all PP ice time. A player moving from PP2 to PP1 can see fantasy output roughly double. Wing positions on PP2 are "fantasy wastelands."

**Verdict: INCLUDE (Tier 1).** PP unit designation and PP TOI are essential. PP role changes are among the strongest leading indicators.

**Sources:** DailyFaceoff.com, LeftWingLock, Natural Stat Trick (PP splits).

-----

### Line Position (Top-6 vs. Bottom-6)

Top-line forwards (~19–22 min TOI) average ~1.03 pts/game vs. 2nd-line ~0.7 pts/game. A player receiving 33% more ice time gets ~33% more fantasy opportunities.

**Verdict: INCLUDE (Tier 2).** Capture via TOI rank or explicit lineup position.

**Sources:** DailyFaceoff.com, LeftWingLock.

-----

### Quality of Competition (QoC) and Quality of Teammates (QoT)

QoC washes out at aggregate level because coaches match lines inconsistently across 30+ opponents. QoT is ~3× more important — variance in linemate quality is much higher. RAPM accounts for all on-ice personnel simultaneously, making separate QoC/QoT metrics unnecessary.

**Verdict: QoC — EXCLUDE (Tier 4). QoT — USE WITH CAUTION (Tier 3).** If using RAPM, both are redundant.

**Sources:** Evolving Hockey (RAPM, QoT/QoC); PuckIQ (WoodMoney tiers).

-----

### Faceoff Win % (FO%)

Highly repeatable skill but with negligible correlation to goals/wins. It takes ~76.5 net faceoff wins to yield +1 goal differential.

**Verdict: INCLUDE for leagues that score faceoff wins (Tier 2); EXCLUDE for standard points leagues (Tier 4).**

**Sources:** NHL.com, Hockey Reference.

-----

## Aging Curves & Career Trajectory

### Peak Ages by Position

|Position  |Peak Age Range            |Notes                                                                                |
|----------|--------------------------|-------------------------------------------------------------------------------------|
|Forwards  |24–28                     |Speed-related skills decline earliest; finishing ability fully developed by NHL entry|
|Defensemen|28–29 (wide plateau to 34)|Less steep decline; offensive D can bloom into 30s                                   |

**Different skills age at different rates.** Speed-related skills decline earliest. Power play ability may decline more slowly. Finishing and shot creation are essentially fully developed when players enter the NHL.

**Survivorship bias** is the biggest challenge in aging curve construction — only the best players survive to older ages. Use the **delta method** (Tango/EvolvingWild) or **Functional PCA** (Cavan & Swartz, SFU, 2023–24) for correction.

**Verdict: Age is a TIER 1 feature.** Include: chronological age, NHL experience years, position-specific aging adjustments.

**Keeper league windows:**

- **Buy:** Ages 20–23 (ELC players with top-6 deployment — 14+ ES min = 43% breakout probability)
- **Hold:** Ages 24–28 for forwards, 24–32 for defensemen
- **Sell:** Ages 28–30 for forwards; 30–32 for defensemen

-----

## Contract & Situational Context

### Contract Year Indicator

Academic research finds **no statistically significant contract year effect** in the NHL (Liehman, 2019/2023). The only notable result: UFAs perform better **two years before** contract expiry (not the final year). Post-extension production declines in 73% of cases where contracts were signed mid-season.

**Verdict: INCLUDE WITH LOW WEIGHT (Tier 3).** Weak positive signal for UFAs under 30; stronger negative signal post-extension.

-----

### ELC Status and Team Context Changes

ELC players who secure top-6 or PP1 roles show dramatically better outcomes. Rookies averaging **14+ ES minutes have a 43% breakout probability vs. 8% for <12 minutes.** Coaching system changes can shift a player's GAR by ≥1 WAR.

**Verdict: INCLUDE as categorical flags (Tier 2).** ELC status + deployment signals are more important than past production for young players.

-----

## NHL EDGE Tracking Data

**Available (free, nhl.com/nhl-edge):**

- Skating speed (max speed, speed bursts at 18+/20+/22+ mph)
- Skating distance per game, by zone
- Shot speed (mph, 100+ mph counts)
- Zone time (offensive/neutral/defensive %)
- Coverage: 2021–22 to 2025–26 (5 seasons)

**Not yet publicly available:** Puck possession time, zone entries/exits, puck touches, acceleration, passing metrics.

**Repeatability:** Team-level burst rates R² = 0.79 year-over-year. Individual shots vs. speed bursts R² = 0.758 (Apex Hockey, 2023–24).

**Limitations:** Only 5 seasons; individual-level fantasy predictiveness unvalidated; ~46 games with data quality issues; no official CSV export.

**Access:** Unofficial APIs (nhl-api-py for Python, nhlscraper for R) or DobberHockey Frozen Tools EDGE Report Generator.

**Verdict: USE WITH CAUTION (Tier 3).** Include skating speed and speed bursts as supplementary aging features. Treat as experimental.

-----

## Data Availability Reference

### Free Sources

|Source            |Data                                                 |Export                                   |
|------------------|-----------------------------------------------------|-----------------------------------------|
|MoneyPuck         |Shot-level xG (124 attrs), player stats, danger zones|CSV download at moneypuck.com/data.htm   |
|Natural Stat Trick|Corsi, SCF%, xG, on/off splits, PP/SH                |HTML scraping (BeautifulSoup, URL params)|
|Hockey Reference  |Traditional stats, Corsi, PDO, career data           |"Get table as CSV" button                |
|NHL EDGE          |Speed, distance, shot speed, zone time               |Unofficial API                           |
|HockeyViz         |Shot maps, aging charts, player impact               |Visual only (no export)                  |
|NHL API           |Raw play-by-play, shift data, rosters                |Direct API calls                         |

### Paid Sources

|Source                        |Cost           |What You Get                              |
|------------------------------|---------------|------------------------------------------|
|Evolving Hockey               |$5/month       |GAR/xGAR/WAR, RAPM — **essential**        |
|The Athletic (Dom Luszczyszyn)|~$8/month      |GSVA projections, player cards            |
|Stathead (HR premium)         |$8/month       |Advanced historical queries               |
|All Three Zones (Sznajder)    |Patreon        |Zone entry/exit data — unique & predictive|
|Sportlogiq                    |Enterprise only|500+ metrics; not accessible              |

-----

*Sources: MoneyPuck, Natural Stat Trick, Evolving Hockey, Hockey Reference, NHL EDGE, Hockey Graphs, Puck Over the Glass, JFresh, DobberHockey, HFBoards analytics research, arxiv.org (Davis 2024), Grantland, RinkHive, The Win Column*
