# Hits & Blocks Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface `hits` and `blocks` in the fantasy scoring pipeline (NHL.com scraper) and `hits_per60`/`blocks_per60` in the ML feature set (NST scraper + feature engineering + FEATURE_NAMES), using Marcel weights `[0.6, 0.25, 0.15]` for physical stats.

**Architecture:** Two data sources feed two pipelines. NHL.com `/realtime` provides raw season totals (`hits`, `blocks`) for the fantasy scoring pipeline. NST per-60 rates (`iHF/60`, `iBLK/60`) feed the Marcel 3-season feature engineering pipeline. Feature engineering gets a per-stat weight override dict so physical stats can use heavier current-season weights without changing the default path.

**Tech Stack:** Python 3.11+, FastAPI, pytest + MagicMock, Supabase (PostgreSQL), httpx, BeautifulSoup4, XGBoost

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `supabase/migrations/005_hits_blocks_per60.sql` | Create | Adds `hits_per60` and `blocks_per60` float columns to `player_stats` |
| `apps/api/scrapers/nst.py` | Modify | Add `iHF/60` → `hits_per60` and `iBLK/60` → `blocks_per60` to `_FLOAT_COL_MAP_ALL` |
| `apps/api/tests/scrapers/fixtures/nst_skaters.html` | Modify | Add `iHF/60` and `iBLK/60` columns with sample values |
| `apps/api/tests/scrapers/test_nst.py` | Modify | Add `TestParseHtmlPhase3Columns` class with 2 tests |
| `apps/api/scrapers/nhl_com.py` | Modify | Add `_NHL_REALTIME_URL`, `_build_realtime_url()`, `_upsert_realtime_stats()`, extend `scrape()` |
| `apps/api/tests/scrapers/test_nhl_com.py` | Modify | Add `TestRealtimeEndpoint` class with 4 tests |
| `apps/api/services/feature_engineering.py` | Modify | Add `PHYSICAL_SEASON_WEIGHTS`, `_STAT_WEIGHT_OVERRIDES`, extend `_WEIGHTED_RATE_STATS`, update `_apply_weighted_rates()` |
| `apps/api/tests/services/test_feature_engineering.py` | Modify | Add 2 weight override tests |
| `apps/api/ml/train.py` | Modify | Add `hits_per60` and `blocks_per60` to `FEATURE_NAMES` |

---

## Task 1: DB Migration

**Files:**
- Create: `supabase/migrations/005_hits_blocks_per60.sql`

- [ ] **Step 1: Write the migration file**

```sql
-- 005_hits_blocks_per60.sql
-- Adds per-60 physical rate columns needed by the ML feature pipeline.
-- hits and blocks (raw totals) already exist from Phase 1.

alter table player_stats
  add column if not exists hits_per60   float,
  add column if not exists blocks_per60 float;
```

- [ ] **Step 2: Apply via Supabase MCP**

Use the `mcp__claude_ai_Supabase__apply_migration` tool with the SQL above, or apply manually in the Supabase dashboard SQL editor.

- [ ] **Step 3: Verify columns exist**

Run via Supabase MCP `execute_sql`:
```sql
select column_name, data_type
from information_schema.columns
where table_name = 'player_stats'
  and column_name in ('hits', 'blocks', 'hits_per60', 'blocks_per60')
order by column_name;
```
Expected: 4 rows returned, all `double precision`.

- [ ] **Step 4: Commit**

```bash
git add supabase/migrations/005_hits_blocks_per60.sql
git commit -m "feat: add hits_per60 and blocks_per60 columns to player_stats"
```

---

## Task 2: NST Scraper — Parse `iHF/60` and `iBLK/60`

**Files:**
- Modify: `apps/api/scrapers/nst.py:94-101` (the `_FLOAT_COL_MAP_ALL` dict)
- Modify: `apps/api/tests/scrapers/fixtures/nst_skaters.html`
- Modify: `apps/api/tests/scrapers/test_nst.py`

- [ ] **Step 1: Write the failing tests**

Add a new test class to `tests/scrapers/test_nst.py`:

```python
class TestParseHtmlPhase3Columns:
    def test_parses_hits_per60(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        row = rows[0]
        assert "hits_per60" in row
        assert row["hits_per60"] == pytest.approx(3.42)

    def test_parses_blocks_per60(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        row = rows[0]
        assert "blocks_per60" in row
        assert row["blocks_per60"] == pytest.approx(0.85)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd apps/api
pytest tests/scrapers/test_nst.py::TestParseHtmlPhase3Columns -v
```
Expected: FAIL — `AssertionError: assert 'hits_per60' in {...}`

- [ ] **Step 3: Update the fixture to add the new columns**

Replace the existing `tests/scrapers/fixtures/nst_skaters.html` header and data rows to add `iHF/60` and `iBLK/60` columns. Full replacement:

```html
<!DOCTYPE html>
<html><body>
<table id="players">
<thead>
<tr>
  <th>#</th>
  <th>Player</th>
  <th>Team</th>
  <th>Position</th>
  <th>GP</th>
  <th>TOI</th>
  <th>SH%</th>
  <th>iCF/60</th>
  <th>ixG/60</th>
  <th>iSCF/60</th>
  <th>First Assists/60</th>
  <th>iHF/60</th>
  <th>iBLK/60</th>
</tr>
</thead>
<tbody>
<tr>
  <td>1</td>
  <td>Connor McDavid</td>
  <td>EDM</td>
  <td>C</td>
  <td>82</td>
  <td>1640.5</td>
  <td>14.2</td>
  <td>17.8</td>
  <td>1.42</td>
  <td>13.5</td>
  <td>3.21</td>
  <td>3.42</td>
  <td>0.85</td>
</tr>
<tr>
  <td>2</td>
  <td>Leon Draisaitl</td>
  <td>EDM</td>
  <td>C</td>
  <td>82</td>
  <td>1580.2</td>
  <td>13.8</td>
  <td>15.4</td>
  <td>1.18</td>
  <td>11.9</td>
  <td>2.87</td>
  <td>2.10</td>
  <td>0.72</td>
</tr>
<tr>
  <td>3</td>
  <td>Nathan MacKinnon</td>
  <td>COL</td>
  <td>C</td>
  <td>80</td>
  <td>1620.8</td>
  <td>13.1</td>
  <td>16.2</td>
  <td>1.31</td>
  <td>12.7</td>
  <td>2.95</td>
  <td>1.87</td>
  <td>0.91</td>
</tr>
</tbody>
</table>
</body></html>
```

- [ ] **Step 4: Add `iHF/60` and `iBLK/60` to `_FLOAT_COL_MAP_ALL` in `scrapers/nst.py`**

Find the `_FLOAT_COL_MAP_ALL` dict (lines ~94-101) and add two entries:

```python
_FLOAT_COL_MAP_ALL: dict[str, str] = {
    "SH%": "sh_pct",
    "iCF/60": "icf_per60",
    "ixG/60": "ixg_per60",
    "iSCF/60": "scf_per60",
    "First Assists/60": "p1_per60",
    "Goals/60": "g_per60",
    "iHF/60": "hits_per60",
    "iBLK/60": "blocks_per60",
}
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
pytest tests/scrapers/test_nst.py -v
```
Expected: All tests PASS including the two new ones.

- [ ] **Step 6: Commit**

```bash
git add apps/api/scrapers/nst.py \
        apps/api/tests/scrapers/fixtures/nst_skaters.html \
        apps/api/tests/scrapers/test_nst.py
git commit -m "feat: parse iHF/60 and iBLK/60 from NST into hits_per60/blocks_per60"
```

---

## Task 3: NHL.com Scraper — Realtime Endpoint

**Files:**
- Modify: `apps/api/scrapers/nhl_com.py`
- Modify: `apps/api/tests/scrapers/test_nhl_com.py`

- [ ] **Step 1: Write the failing tests**

Add a new test class to `tests/scrapers/test_nhl_com.py`. The existing `_make_response` and `_mock_db` helpers are already defined and can be reused.

Add after the existing `SEASON` constant near the top, add a realtime player fixture:

```python
NHL_REALTIME_PLAYER_1 = {
    "playerId": 8478402,  # same ID as NHL_PLAYER_1 (McDavid)
    "hits": 34,
    "blockedShots": 12,
}
```

Add the new test class:

```python
class TestRealtimeEndpoint:
    def test_build_realtime_url_contains_realtime_path(self) -> None:
        url = NhlComScraper()._build_realtime_url(SEASON)
        assert "skater/realtime" in url

    @pytest.mark.asyncio
    async def test_upserts_hits_and_blocks(self) -> None:
        """Two-pass scrape: summary then realtime. Hits/blocks land in player_stats."""
        mock_http = AsyncMock()
        mock_http.get.side_effect = [
            # robots.txt
            httpx.Response(200, text="User-agent: *\nAllow: /",
                           request=httpx.Request("GET", "http://x")),
            # summary page 1 (less than PAGE_SIZE → done)
            _make_response({"data": [NHL_PLAYER_1], "total": 1}),
            # realtime page 1
            _make_response({"data": [NHL_REALTIME_PLAYER_1], "total": 1}),
        ]
        db = _mock_db()
        scraper = NhlComScraper(http=mock_http)
        await scraper.scrape(SEASON, db)
        upsert_calls = str(db.table.return_value.upsert.call_args_list)
        assert "'hits': 34" in upsert_calls
        assert "'blocks': 12" in upsert_calls

    @pytest.mark.asyncio
    async def test_realtime_skips_player_not_in_summary(self) -> None:
        """Realtime player whose ID wasn't in the summary pass should be skipped."""
        realtime_unknown = {"playerId": 9999999, "hits": 100, "blockedShots": 50}
        mock_http = AsyncMock()
        mock_http.get.side_effect = [
            httpx.Response(200, text="User-agent: *\nAllow: /",
                           request=httpx.Request("GET", "http://x")),
            _make_response({"data": [NHL_PLAYER_1], "total": 1}),
            _make_response({"data": [realtime_unknown], "total": 1}),
        ]
        db = _mock_db()
        scraper = NhlComScraper(http=mock_http)
        await scraper.scrape(SEASON, db)
        upsert_calls = str(db.table.return_value.upsert.call_args_list)
        assert "'hits': 100" not in upsert_calls

    @pytest.mark.asyncio
    async def test_realtime_skips_when_no_hits_or_blocks(self) -> None:
        """Realtime row with neither hits nor blockedShots should not trigger upsert."""
        realtime_empty = {"playerId": 8478402}  # no hits, no blockedShots
        mock_http = AsyncMock()
        mock_http.get.side_effect = [
            httpx.Response(200, text="User-agent: *\nAllow: /",
                           request=httpx.Request("GET", "http://x")),
            _make_response({"data": [NHL_PLAYER_1], "total": 1}),
            _make_response({"data": [realtime_empty], "total": 1}),
        ]
        db = _mock_db()
        scraper = NhlComScraper(http=mock_http)
        await scraper.scrape(SEASON, db)
        # player_stats upsert is still called once (from the summary pass for gp/g/a/pts)
        # but should NOT have a second call with hits/blocks keys
        upsert_calls = str(db.table.return_value.upsert.call_args_list)
        assert "'hits'" not in upsert_calls
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/scrapers/test_nhl_com.py::TestRealtimeEndpoint -v
```
Expected: FAIL — `AttributeError: 'NhlComScraper' object has no attribute '_build_realtime_url'`

- [ ] **Step 3: Implement the realtime endpoint in `scrapers/nhl_com.py`**

After the existing `_NHL_STATS_URL` constant, add:

```python
_NHL_REALTIME_URL = "https://api.nhle.com/stats/rest/en/skater/realtime"
```

After the existing `_build_url()` method, add `_build_realtime_url()`:

```python
def _build_realtime_url(self, season: str, start: int = 0) -> str:
    sort = json.dumps([{"property": "hits", "direction": "DESC"}])
    expr = f"seasonId={self._season_id(season)} and gameTypeId=2"
    return (
        f"{_NHL_REALTIME_URL}?isAggregate=false&isGame=false"
        f"&sort={sort}&start={start}&limit={self.PAGE_SIZE}"
        f"&cayenneExp={expr}"
    )
```

After `_upsert_player_stats()`, add `_upsert_realtime_stats()`:

```python
def _upsert_realtime_stats(
    self, db: Any, player_id: str, season: str, player: dict[str, Any]
) -> None:
    int_fields = {"hits": "hits", "blockedShots": "blocks"}
    stats: dict[str, Any] = {}
    for api_key, col in int_fields.items():
        if (val := player.get(api_key)) is not None:
            stats[col] = int(val)
    if not stats:
        return
    db.table("player_stats").upsert(
        {"player_id": player_id, "season": season, **stats},
        on_conflict="player_id,season",
    ).execute()
```

- [ ] **Step 4: Modify `scrape()` to build `nhl_id_map` and run the realtime pass**

The current `scrape()` method loops over the summary endpoint. Extend it as follows:

```python
async def scrape(self, season: str, db: Any) -> int:  # noqa: D102
    if not await self._check_robots_txt(_NHL_STATS_URL):
        raise RobotsDisallowedError(f"robots.txt disallows scraping {_NHL_STATS_URL}")

    source_id = self._upsert_source(db)
    rows_upserted = 0
    start = 0
    nhl_id_map: dict[str, str] = {}  # nhl_id (str) → internal player_id (uuid)

    while True:
        url = self._build_url(season, start)
        response = await self._get_with_retry(url)
        players: list[dict[str, Any]] = response.json().get("data", [])

        if not players:
            break

        for offset, player in enumerate(players):
            rank = start + offset + 1
            player_id = self._upsert_player(db, player)
            nhl_id_map[str(player["playerId"])] = player_id
            self._upsert_ranking(db, player_id, source_id, rank, season)
            self._upsert_player_stats(db, player_id, season, player)
            rows_upserted += 1

        if len(players) < self.PAGE_SIZE:
            break

        start += self.PAGE_SIZE
        await asyncio.sleep(self.MIN_DELAY_SECONDS)

    # Realtime pass — hits + blocked shots
    start = 0
    while True:
        url = self._build_realtime_url(season, start)
        response = await self._get_with_retry(url)
        players = response.json().get("data", [])

        if not players:
            break

        for player in players:
            nhl_id = str(player["playerId"])
            player_id = nhl_id_map.get(nhl_id)
            if player_id is None:
                continue
            self._upsert_realtime_stats(db, player_id, season, player)

        if len(players) < self.PAGE_SIZE:
            break

        start += self.PAGE_SIZE
        await asyncio.sleep(self.MIN_DELAY_SECONDS)

    logger.info("NHL.com: upserted %d rankings for %s", rows_upserted, season)
    return rows_upserted
```

- [ ] **Step 5: Run all NHL.com tests**

```bash
pytest tests/scrapers/test_nhl_com.py -v
```
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/scrapers/nhl_com.py \
        apps/api/tests/scrapers/test_nhl_com.py
git commit -m "feat: add NHL.com realtime endpoint pass for hits and blocks"
```

---

## Task 4: Feature Engineering — Physical Stat Weight Overrides

**Files:**
- Modify: `apps/api/services/feature_engineering.py`
- Modify: `apps/api/tests/services/test_feature_engineering.py`

- [ ] **Step 1: Write the failing tests**

Add two new test functions to `tests/services/test_feature_engineering.py`. Add them after the existing test classes. The `_make_row` helper is already defined in that file and accepts keyword args.

```python
class TestPhysicalStatWeights:
    def test_hits_per60_uses_physical_weights(self) -> None:
        """hits_per60 should use [0.6, 0.25, 0.15], not [0.5, 0.3, 0.2]."""
        # Three seasons newest-first, each with toi_ev above threshold
        rows = [
            {**_make_row(season=2025), "hits_per60": 4.0},  # current (weight 0.6)
            {**_make_row(season=2024), "hits_per60": 2.0},  # yr -1  (weight 0.25)
            {**_make_row(season=2023), "hits_per60": 1.0},  # yr -2  (weight 0.15)
        ]
        result = _apply_weighted_rates(rows)
        # Normalized: 0.6/1.0=0.6, 0.25/1.0=0.25, 0.15/1.0=0.15
        expected = 0.6 * 4.0 + 0.25 * 2.0 + 0.15 * 1.0
        assert result["hits_per60"] == pytest.approx(expected)

    def test_standard_stats_unaffected_by_override(self) -> None:
        """icf_per60 should still use [0.5, 0.3, 0.2] weights."""
        rows = [
            {**_make_row(season=2025), "icf_per60": 18.0},  # current (0.5)
            {**_make_row(season=2024), "icf_per60": 14.0},  # yr -1   (0.3)
            {**_make_row(season=2023), "icf_per60": 10.0},  # yr -2   (0.2)
        ]
        result = _apply_weighted_rates(rows)
        # Normalized: 0.5/1.0=0.5, 0.3/1.0=0.3, 0.2/1.0=0.2
        expected = 0.5 * 18.0 + 0.3 * 14.0 + 0.2 * 10.0
        assert result["icf_per60"] == pytest.approx(expected)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/services/test_feature_engineering.py::TestPhysicalStatWeights -v
```
Expected: FAIL — `KeyError: 'hits_per60'` (stat not in `_WEIGHTED_RATE_STATS` yet)

- [ ] **Step 3: Implement the changes in `services/feature_engineering.py`**

**3a. Add `PHYSICAL_SEASON_WEIGHTS` constant** after `SEASON_WEIGHTS`:

```python
SEASON_WEIGHTS: list[float] = [0.5, 0.3, 0.2]
PHYSICAL_SEASON_WEIGHTS: list[float] = [0.6, 0.25, 0.15]
```

**3b. Add `_STAT_WEIGHT_OVERRIDES` dict** after `SEASON_WEIGHTS`/`PHYSICAL_SEASON_WEIGHTS`:

```python
_STAT_WEIGHT_OVERRIDES: dict[str, list[float]] = {
    "hits_per60": PHYSICAL_SEASON_WEIGHTS,
    "blocks_per60": PHYSICAL_SEASON_WEIGHTS,
}
```

**3c. Extend `_WEIGHTED_RATE_STATS`** to include the two new stats:

```python
_WEIGHTED_RATE_STATS: list[str] = [
    "icf_per60", "ixg_per60", "xgf_pct_5v5", "cf_pct_adj",
    "scf_per60", "scf_pct", "p1_per60", "toi_ev", "toi_pp", "toi_sh",
    "hits_per60",    # physical stickiness signal
    "blocks_per60",  # physical stickiness signal
]
```

**3d. Update `_apply_weighted_rates()`** to compute weights per-stat (move weight calculation inside the loop):

```python
def _apply_weighted_rates(rows: list[dict[str, Any]]) -> dict[str, Any]:
    qualifying = [r for r in rows if (r.get("toi_ev") or 0.0) >= TOI_THRESHOLD]
    result: dict[str, Any] = {stat: None for stat in _WEIGHTED_RATE_STATS}
    result["_qualifying_count"] = len(qualifying)
    if not qualifying:
        return result
    for stat in _WEIGHTED_RATE_STATS:
        base_weights = _STAT_WEIGHT_OVERRIDES.get(stat, SEASON_WEIGHTS)
        raw_w = base_weights[: len(qualifying)]
        norm = [w / sum(raw_w) for w in raw_w]
        stat_pairs = [
            (norm[i], row[stat])
            for i, row in enumerate(qualifying)
            if row.get(stat) is not None
        ]
        if not stat_pairs:
            result[stat] = None
            continue
        stat_weight_total = sum(w for w, _ in stat_pairs)
        result[stat] = sum((w / stat_weight_total) * v for w, v in stat_pairs)
    return result
```

- [ ] **Step 4: Run all feature engineering tests**

```bash
pytest tests/services/test_feature_engineering.py -v
```
Expected: All tests PASS including the two new ones.

- [ ] **Step 5: Commit**

```bash
git add apps/api/services/feature_engineering.py \
        apps/api/tests/services/test_feature_engineering.py
git commit -m "feat: add physical stat Marcel weight overrides for hits_per60/blocks_per60"
```

---

## Task 5: ML Training — Add to FEATURE_NAMES

**Files:**
- Modify: `apps/api/ml/train.py`

- [ ] **Step 1: Add `hits_per60` and `blocks_per60` to `FEATURE_NAMES`**

Find the `FEATURE_NAMES` list (around line 40-62 in `ml/train.py`) and add the two new features:

```python
FEATURE_NAMES: list[str] = [
    "icf_per60", "ixg_per60", "xgf_pct_5v5", "cf_pct_adj", "scf_per60",
    "scf_pct", "p1_per60", "toi_ev", "toi_pp", "g_per60", "ixg_per60_curr",
    "g_minus_ixg", "sh_pct_delta", "pdo", "pp_unit", "oi_sh_pct",
    "elc_flag", "contract_year_flag", "post_extension_flag", "age", "icf_per60_delta",
    "hits_per60",    # Marcel-weighted physical rate (Tier 3)
    "blocks_per60",  # Marcel-weighted physical rate (Tier 3)
]
```

Total: 23 features.

- [ ] **Step 2: Run the full test suite to confirm nothing regressed**

```bash
cd apps/api
pytest -q
```
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add apps/api/ml/train.py
git commit -m "feat: add hits_per60 and blocks_per60 to ML FEATURE_NAMES (23 features)"
```

---

## Task 6: Backfill History & Re-train

These steps run after all code is merged and the Supabase migration is applied.

- [ ] **Step 1: Backfill NST history** (populates `hits_per60`/`blocks_per60` for all seasons)

```bash
cd apps/api
python -m scrapers.nst --history
```
Expected output ends with: `NST history: N total rows upserted`

- [ ] **Step 2: Backfill NHL.com history** (populates `hits`/`blocks` raw totals)

```bash
python -m scrapers.nhl_com --history
```
Expected output ends with: `NHL.com history: N total rows upserted`

- [ ] **Step 3: Verify columns are populated in Supabase**

Run via Supabase MCP or dashboard:
```sql
select hits, blocks, hits_per60, blocks_per60
from player_stats
where season = '2025-26' and hits is not null
limit 5;
```
Expected: all four columns non-null for active players.

- [ ] **Step 4: Run training**

```bash
python -m ml.train --season 2026-27
```

---

## Verification

Run the full test suite after Task 5 completes and before beginning Task 6:

```bash
cd apps/api
pytest tests/scrapers/test_nst.py tests/scrapers/test_nhl_com.py tests/services/test_feature_engineering.py -v
```

Expected: All tests green, including:
- `TestParseHtmlPhase3Columns::test_parses_hits_per60`
- `TestParseHtmlPhase3Columns::test_parses_blocks_per60`
- `TestRealtimeEndpoint::test_build_realtime_url_contains_realtime_path`
- `TestRealtimeEndpoint::test_upserts_hits_and_blocks`
- `TestRealtimeEndpoint::test_realtime_skips_player_not_in_summary`
- `TestRealtimeEndpoint::test_realtime_skips_when_no_hits_or_blocks`
- `TestPhysicalStatWeights::test_hits_per60_uses_physical_weights`
- `TestPhysicalStatWeights::test_standard_stats_unaffected_by_override`
