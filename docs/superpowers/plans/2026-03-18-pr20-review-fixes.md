# PR #20 Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Address all P1/P2 bot comments and Critical/Important reviewer issues on PR #20 (Yahoo, Fantrax, platform_positions, schedule_scores scrapers).

**Architecture:** Seven targeted fixes across five files. The two `player_details("all")` bugs are consolidated via a shared `fetch_all_yahoo_nhl_players()` helper in `scrapers/projection/yahoo.py` that both callers import. All other fixes are in-place changes to the affected files.

**Tech Stack:** Python 3.11, FastAPI, httpx (async), yahoo-fantasy-api, pytest, ruff

---

## Files Changed

| File | Change |
|---|---|
| `scrapers/projection/yahoo.py` | Extract bulk fetch helper; add `BaseScraper` MRO + robots.txt; guard `update_last_successful_scrape` |
| `scrapers/platform_positions.py` | Use shared Yahoo helper; replace bare `httpx.get` with retry helper; add unmatched logging |
| `scrapers/projection/fantrax.py` | Add `BaseScraper` MRO + robots.txt; fix sync→async HTTP; guard `update_last_successful_scrape` |
| `scrapers/schedule_scores.py` | Abort on empty schedule; derive season dynamically |
| `.github/workflows/scrape-platform-data.yml` | Clarify workflow name + cron comment |
| `tests/scrapers/projection/test_yahoo.py` | Use `monkeypatch` for token mutation; add robots.txt test |
| `tests/scrapers/projection/test_fantrax.py` | Use `monkeypatch` for token mutation; add robots.txt test |
| `tests/scrapers/test_schedule_scores.py` | Add empty-schedule abort test |
| `tests/scrapers/test_platform_positions.py` | Add unmatched-logging test for Yahoo positions |

---

## Task 1: Extract shared Yahoo bulk-fetch helper and fix `player_details("all")`

Both `YahooScraper._fetch_yahoo_players()` (yahoo.py:93) and `ingest_yahoo_positions()` (platform_positions.py:125) call `game.to_league(game.league_ids()[0]).player_details("all")`. This is a **name search** (returns only a handful of players), not a bulk fetch. Fix by extracting a proper paginated helper into `yahoo.py` and importing it from `platform_positions.py`.

> **Before coding:** Use Context7 MCP (`mcp__claude_ai_Context7__query-docs` with `yahoo-fantasy-api`) to verify the correct bulk player fetch approach. The library likely exposes `game.player_stats()` with `start`/`count` pagination, or `league.free_agents()`+`league.taken_players()`. Confirm the exact method signature before implementing.

**Files:**
- Modify: `apps/api/scrapers/projection/yahoo.py`
- Modify: `apps/api/scrapers/platform_positions.py`
- Test: `apps/api/tests/scrapers/projection/test_yahoo.py`
- Test: `apps/api/tests/scrapers/test_platform_positions.py`

- [ ] **Step 1: Write failing test — bulk fetch uses pagination, not `player_details("all")`**

In `tests/scrapers/projection/test_yahoo.py`, add:

```python
def test_fetch_yahoo_players_uses_pagination(monkeypatch) -> None:
    """_fetch_yahoo_players must paginate via game.player_stats(), not call player_details('all')."""
    import yahoo_fantasy_api as yfa

    player_stats_calls: list[dict] = []
    player_details_calls: list = []

    class FakeLeague:
        def player_details(self, arg):
            player_details_calls.append(arg)
            return []

    class FakeGame:
        def league_ids(self):
            return ["12345"]
        def to_league(self, lid):
            return FakeLeague()
        def player_stats(self, ids, req_type="season", start=0, count=25):
            player_stats_calls.append({"start": start, "count": count})
            return []  # empty → pagination loop exits immediately

    monkeypatch.setattr(yfa, "OAuth2", lambda *a, **kw: MagicMock())
    monkeypatch.setattr(yfa, "Game", lambda *a, **kw: FakeGame())
    monkeypatch.setattr("core.config.settings.yahoo_oauth_refresh_token", "tok")

    from scrapers.projection.yahoo import fetch_all_yahoo_nhl_players
    fetch_all_yahoo_nhl_players("tok")

    # Must use pagination via player_stats(), never player_details("all")
    assert len(player_stats_calls) >= 1, "Expected player_stats() to be called for pagination"
    assert "all" not in player_details_calls, "Must not use player_details('all') name-search"
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd apps/api && pytest tests/scrapers/projection/test_yahoo.py::test_fetch_yahoo_players_uses_pagination -v
```

Expected: FAIL — `fetch_all_yahoo_nhl_players` doesn't exist yet, or calls `player_details("all")` instead of `player_stats()`

- [ ] **Step 3: Implement `fetch_all_yahoo_nhl_players()` module-level helper in `yahoo.py`**

Replace the body of `_fetch_yahoo_players` and extract the OAuth setup into a reusable module-level function:

```python
def fetch_all_yahoo_nhl_players(oauth_token: str) -> list[dict[str, Any]]:
    """Fetch all NHL players with stats from Yahoo Fantasy API using pagination.

    Uses the yahoo-fantasy-api library. Does NOT go through a user league —
    queries the NHL game resource directly to avoid the name-search bug in
    League.player_details(str).

    Args:
        oauth_token: YAHOO_OAUTH_REFRESH_TOKEN value from settings.

    Returns:
        List of raw Yahoo player dicts (name, eligible_positions, player_stats).
    """
    import yahoo_fantasy_api as yfa  # type: ignore[import-untyped]

    oauth = yfa.OAuth2(None, None, from_file=None)
    oauth.refresh_access_token(oauth_token)
    game = yfa.Game(oauth, "nhl")

    # Paginate through all NHL players using start/count.
    # Yahoo caps responses at 25 players per call; iterate until empty.
    all_players: list[dict[str, Any]] = []
    start = 0
    count = 25
    while True:
        batch = game.player_stats([], req_type="season", start=start, count=count)
        if not batch:
            break
        all_players.extend(batch)
        if len(batch) < count:
            break
        start += count
    return all_players
```

> **Note:** Verify the exact method name and parameters with Context7 before finalising. If `game.player_stats()` does not accept `start`/`count`, use the correct pagination API from the docs.

Then update `YahooScraper._fetch_yahoo_players` to delegate:

```python
def _fetch_yahoo_players(self) -> list[dict[str, Any]]:
    """Fetch all NHL players with projected stats from Yahoo Fantasy API."""
    from core.config import settings
    return fetch_all_yahoo_nhl_players(settings.yahoo_oauth_refresh_token)
```

And update `platform_positions.py` to import and use the helper:

```python
# At top of file, add:
from scrapers.projection.yahoo import fetch_all_yahoo_nhl_players

# Replace the try block in ingest_yahoo_positions():
    try:
        yahoo_players = fetch_all_yahoo_nhl_players(settings.yahoo_oauth_refresh_token)
    except Exception as exc:
        logger.error("Yahoo positions fetch failed: %s", exc)
        return 0
```

Remove the inline `import yahoo_fantasy_api`, OAuth setup, and `game.to_league(...).player_details("all")` from `ingest_yahoo_positions`.

- [ ] **Step 4: Run tests to verify fix**

```bash
cd apps/api && pytest tests/scrapers/projection/test_yahoo.py tests/scrapers/test_platform_positions.py -v
```

Expected: all green including the new test.

- [ ] **Step 5: Commit**

```bash
git add apps/api/scrapers/projection/yahoo.py apps/api/scrapers/platform_positions.py \
        apps/api/tests/scrapers/projection/test_yahoo.py \
        apps/api/tests/scrapers/test_platform_positions.py
git commit -m "fix(scrapers): replace player_details(\"all\") with paginated bulk fetch

Extract fetch_all_yahoo_nhl_players() helper; both YahooScraper and
ingest_yahoo_positions now paginate via game.player_stats() instead of
calling player_details(\"all\") which is a name-search cap of ~handful players.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Add `BaseScraper` MRO + robots.txt to `YahooScraper`; guard `update_last_successful_scrape`

`YahooScraper` inherits only `BaseProjectionScraper`. It needs `BaseScraper` in its MRO so it can call `_check_robots_txt()` before making network calls. Also guard `update_last_successful_scrape` with `if upserted > 0`.

**Files:**
- Modify: `apps/api/scrapers/projection/yahoo.py`
- Test: `apps/api/tests/scrapers/projection/test_yahoo.py`

- [ ] **Step 1: Write failing test — robots.txt called in scrape()**

Add inside the existing `TestScrape` class in `test_yahoo.py`:

```python
    @pytest.mark.asyncio
    async def test_scrape_checks_robots_txt(self, monkeypatch) -> None:
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "src-1"}]
        mock_db.table.return_value.select.return_value.execute.return_value.data = []

        scraper = YahooScraper()
        robots_calls: list[str] = []

        async def fake_check_robots(url: str) -> bool:
            robots_calls.append(url)
            return True

        monkeypatch.setattr("core.config.settings.yahoo_oauth_refresh_token", "tok")
        monkeypatch.setattr(scraper, "_check_robots_txt", fake_check_robots)
        with patch.object(scraper, "_fetch_yahoo_players", return_value=[]):
            await scraper.scrape("2025-26", mock_db)

        assert len(robots_calls) == 1, "Expected _check_robots_txt to be called once"
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd apps/api && pytest "tests/scrapers/projection/test_yahoo.py::TestScrape::test_scrape_checks_robots_txt" -v
```

Expected: FAIL (AttributeError — `YahooScraper` has no `_check_robots_txt` because `BaseScraper` not yet in MRO)

- [ ] **Step 3: Add `BaseScraper` to MRO and call `_check_robots_txt` in `scrape()`**

Change class definition:

```python
from scrapers.base import BaseScraper, RobotsDisallowedError

class YahooScraper(BaseScraper, BaseProjectionScraper):
```

Add robots.txt check at the top of `scrape()` (before the token check, since `BaseScraper.__init__` sets up the HTTP client):

```python
async def scrape(self, season: str, db: Any) -> int:
    from core.config import settings

    if not settings.yahoo_oauth_refresh_token:
        logger.warning("Yahoo: no OAuth refresh token configured — skipping")
        return 0

    YAHOO_API_URL = "https://fantasysports.yahooapis.com/"
    allowed = await self._check_robots_txt(YAHOO_API_URL)
    if not allowed:
        raise RobotsDisallowedError(f"robots.txt disallows scraping {YAHOO_API_URL}")

    # ... rest of scrape unchanged
```

Also change the `update_last_successful_scrape` call:

```python
    # was: update_last_successful_scrape(db, source_id)
    if upserted > 0:
        update_last_successful_scrape(db, source_id)
```

- [ ] **Step 4: Run all Yahoo tests**

```bash
cd apps/api && pytest tests/scrapers/projection/test_yahoo.py -v
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add apps/api/scrapers/projection/yahoo.py apps/api/tests/scrapers/projection/test_yahoo.py
git commit -m "fix(scrapers): add BaseScraper MRO and robots.txt check to YahooScraper

Also guard update_last_successful_scrape with if upserted > 0 to avoid
stamping a no-op run as successful (consistent with HashtagHockeyScraper).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Fix `FantraxScraper` — async HTTP, `BaseScraper` MRO, robots.txt, `update_last_successful_scrape` guard

`_fetch_fantrax_players` uses synchronous `httpx.get` inside an async method (blocks event loop). Add `BaseScraper` to MRO, replace sync call with `await self._get_with_retry()`, add robots.txt check, and guard `update_last_successful_scrape`.

**Files:**
- Modify: `apps/api/scrapers/projection/fantrax.py`
- Test: `apps/api/tests/scrapers/projection/test_fantrax.py`

- [ ] **Step 1: Write failing test — robots.txt called in scrape()**

```python
    # Add inside the existing TestScrape class in test_fantrax.py:
    @pytest.mark.asyncio
    async def test_scrape_checks_robots_txt(self, monkeypatch) -> None:
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "src-1"}]
        mock_db.table.return_value.select.return_value.execute.return_value.data = []

        scraper = FantraxScraper()
        robots_calls: list[str] = []

        async def fake_check_robots(url: str) -> bool:
            robots_calls.append(url)
            return True

        monkeypatch.setattr("core.config.settings.fantrax_session_token", "tok")
        monkeypatch.setattr(scraper, "_check_robots_txt", fake_check_robots)
        with patch.object(scraper, "_fetch_fantrax_players", new=AsyncMock(return_value=[])):
            await scraper.scrape("2025-26", mock_db)

        assert len(robots_calls) == 1
```

Also add `from unittest.mock import AsyncMock` to the imports at the top of `test_fantrax.py`.

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd apps/api && pytest "tests/scrapers/projection/test_fantrax.py::TestScrape::test_scrape_checks_robots_txt" -v
```

Expected: FAIL (AttributeError — `FantraxScraper` has no `_check_robots_txt`)

- [ ] **Step 3: Fix `fantrax.py`**

Change class definition:

```python
from scrapers.base import BaseScraper, RobotsDisallowedError

class FantraxScraper(BaseScraper, BaseProjectionScraper):
```

Change `_fetch_fantrax_players` from a sync method to async, replacing `httpx.get` with `self._get_with_retry`:

```python
async def _fetch_fantrax_players(self) -> list[dict[str, Any]]:
    """Fetch player projection data from Fantrax API."""
    from core.config import settings

    if not settings.fantrax_session_token:
        return []

    resp = await self._get_with_retry(
        FANTRAX_API_URL,
        params={"msgs": "getPlayersTable"},
        cookies={"fantrax.session": settings.fantrax_session_token},
    )
    data = resp.json()
    return data.get("responses", [{}])[0].get("data", {}).get("rows", [])
```

Update `scrape()` to:
1. Await `_fetch_fantrax_players()`
2. Add robots.txt check
3. Guard `update_last_successful_scrape`

```python
async def scrape(self, season: str, db: Any) -> int:
    from core.config import settings

    if not settings.fantrax_session_token:
        logger.warning("Fantrax: no session token configured — skipping")
        return 0

    if not AUTO_SCRAPE:
        logger.info("Fantrax: AUTO_SCRAPE disabled — use paste/upload mode")
        return 0

    allowed = await self._check_robots_txt(FANTRAX_API_URL)
    if not allowed:
        raise RobotsDisallowedError(f"robots.txt disallows scraping {FANTRAX_API_URL}")

    source_id = upsert_source(db, self.SOURCE_NAME, self.DISPLAY_NAME)
    players, aliases = fetch_players_and_aliases(db)
    matcher = PlayerMatcher(players, aliases)

    try:
        fantrax_players = await self._fetch_fantrax_players()
    except Exception as exc:
        logger.error("Fantrax: API fetch failed: %s", exc)
        return 0

    upserted = 0
    for raw in fantrax_players:
        row = self._parse_player(raw)
        player_name = row.pop("player_name", "")
        if not player_name:
            continue
        player_id = matcher.resolve(player_name)
        if player_id is None:
            log_unmatched(db, self.SOURCE_NAME, player_name, season)
            continue
        upsert_projection_row(db, player_id, source_id, season, row)
        upserted += 1

    if upserted > 0:
        update_last_successful_scrape(db, source_id)
    logger.info("%s: upserted %d rows for %s", self.DISPLAY_NAME, upserted, season)
    return upserted
```

Also remove the top-level `import httpx` since `BaseScraper` owns the HTTP client now.

- [ ] **Step 4: Update `test_fantrax.py` — patch is now `async`**

The existing `patch.object(scraper, "_fetch_fantrax_players", return_value=[])` patches a sync method. Now that `_fetch_fantrax_players` is async, replace with `AsyncMock`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

# In test_returns_int:
with patch.object(scraper, "_fetch_fantrax_players", new=AsyncMock(return_value=[])):
    ...
```

- [ ] **Step 5: Run all Fantrax tests**

```bash
cd apps/api && pytest tests/scrapers/projection/test_fantrax.py -v
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add apps/api/scrapers/projection/fantrax.py apps/api/tests/scrapers/projection/test_fantrax.py
git commit -m "fix(scrapers): fix FantraxScraper — async HTTP, BaseScraper MRO, robots.txt

Replace blocking sync httpx.get with await self._get_with_retry().
Add BaseScraper to MRO so robots.txt and retry helpers are available.
Guard update_last_successful_scrape with if upserted > 0.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Fix ESPN retry + Yahoo positions unmatched logging in `platform_positions.py`

`_fetch_espn_players` uses a bare `httpx.get` (no retry, no `BaseScraper`). Since `platform_positions.py` is not a scraper class, add a simple retry loop inline (3 attempts, exponential backoff). Also add an `unmatched` counter to `ingest_yahoo_positions` (ESPN already has one; Yahoo silently drops unresolved players).

**Files:**
- Modify: `apps/api/scrapers/platform_positions.py`
- Test: `apps/api/tests/scrapers/test_platform_positions.py`

- [ ] **Step 1: Write failing test — unmatched logged for Yahoo positions**

```python
def test_yahoo_positions_logs_unmatched(monkeypatch, caplog) -> None:
    import logging
    from scrapers.platform_positions import ingest_yahoo_positions

    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.execute.return_value.data = []

    yahoo_player = {
        "name": {"full": "Unknown Player XYZ"},
        "eligible_positions": [{"position": "C"}],
    }
    monkeypatch.setattr("core.config.settings.yahoo_oauth_refresh_token", "tok")
    monkeypatch.setattr(
        "scrapers.platform_positions.fetch_all_yahoo_nhl_players",
        lambda token: [yahoo_player],
    )

    with caplog.at_level(logging.INFO, logger="scrapers.platform_positions"):
        ingest_yahoo_positions(mock_db)

    assert "unmatched" in caplog.text
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd apps/api && pytest tests/scrapers/test_platform_positions.py::test_yahoo_positions_logs_unmatched -v
```

Expected: FAIL

- [ ] **Step 3: Add retry loop to `_fetch_espn_players` and unmatched counter to `ingest_yahoo_positions`**

Replace `_fetch_espn_players`:

```python
def _fetch_espn_players() -> list[dict[str, Any]]:
    """Fetch all NHL players from ESPN Fantasy API with exponential-backoff retry."""
    import time
    max_retries = 3
    retry_statuses = {429, 500, 502, 503, 504}
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        if attempt > 0:
            time.sleep(2 ** (attempt - 1))
        try:
            resp = httpx.get(ESPN_PLAYERS_URL, timeout=30.0)
            if resp.status_code in retry_statuses:
                last_exc = httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}", request=resp.request, response=resp
                )
                continue
            resp.raise_for_status()
            return resp.json().get("players", [])
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in retry_statuses:
                raise
            last_exc = exc
        except httpx.RequestError as exc:
            last_exc = exc
    raise last_exc or RuntimeError("ESPN fetch: max retries exceeded")
```

Add `unmatched` counter + log to `ingest_yahoo_positions`:

```python
    upserted = 0
    unmatched = 0   # add this
    for yp in yahoo_players:
        name = yp.get("name", {}).get("full", "")
        player_id = matcher.resolve(name)
        if player_id is None:
            unmatched += 1   # add this
            continue
        ...

    logger.info("Yahoo positions: upserted=%d unmatched=%d", upserted, unmatched)  # update
```

- [ ] **Step 4: Run all platform_positions tests**

```bash
cd apps/api && pytest tests/scrapers/test_platform_positions.py -v
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add apps/api/scrapers/platform_positions.py apps/api/tests/scrapers/test_platform_positions.py
git commit -m "fix(scrapers): add ESPN retry logic and Yahoo positions unmatched logging

_fetch_espn_players now retries with exponential backoff on 429/5xx.
ingest_yahoo_positions now logs unmatched count (consistent with ESPN).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Abort `schedule_scores.ingest()` when schedule is empty; derive season dynamically

**P1:** If `_fetch_season_schedule()` returns `[]` (upstream outage or schema change), `ingest()` currently writes `total_games=0 / schedule_score=0.0` for every player, wiping existing data. Add an early-abort guard.

**P2:** `__main__` block hardcodes `"2025-26"`. Use `settings.current_season` so the yearly September 1 run writes to the correct season automatically.

**Files:**
- Modify: `apps/api/scrapers/schedule_scores.py`
- Test: `apps/api/tests/scrapers/test_schedule_scores.py`

- [ ] **Step 1: Write failing test — ingest aborts on empty schedule**

```python
@pytest.mark.asyncio
async def test_ingest_aborts_on_empty_schedule() -> None:
    """ingest() must not upsert any rows when _fetch_season_schedule returns []."""
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.execute.return_value.data = [
        {"id": "p1", "team": "EDM"},
    ]

    with patch(
        "scrapers.schedule_scores._fetch_season_schedule",
        new=AsyncMock(return_value=[]),
    ):
        await ingest("2025-26", mock_db)

    # No upsert should have been called
    mock_db.table.return_value.upsert.assert_not_called()
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd apps/api && pytest tests/scrapers/test_schedule_scores.py::test_ingest_aborts_on_empty_schedule -v
```

Expected: FAIL (upsert IS called currently)

- [ ] **Step 3: Add guard to `ingest()` and fix `__main__`**

In `ingest()`, after fetching the schedule, add:

```python
async def ingest(season: str, db: Any) -> None:
    schedule = await _fetch_season_schedule(season)
    if not schedule:
        logger.warning(
            "Schedule scores: no game days fetched for %s — aborting to preserve existing data",
            season,
        )
        return
    logger.info("Fetched %d game days for %s", len(schedule), season)
    # ... rest unchanged
```

In `__main__`:

```python
if __name__ == "__main__":
    from core.config import settings
    from core.dependencies import get_db
    asyncio.run(ingest(settings.current_season, get_db()))
```

- [ ] **Step 4: Run all schedule_scores tests**

```bash
cd apps/api && pytest tests/scrapers/test_schedule_scores.py -v
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add apps/api/scrapers/schedule_scores.py apps/api/tests/scrapers/test_schedule_scores.py
git commit -m "fix(scrapers): abort schedule scores write on empty fetch; derive season dynamically

Guard ingest() against upstream outages: if _fetch_season_schedule returns
[], log a warning and return without touching existing schedule_scores rows.
__main__ now uses settings.current_season instead of hardcoded '2025-26'.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Fix GitHub Actions workflow name and cron comment

The workflow is named "Ingest Platform Data (Positions + Schedule Scores)" and the cron is `"0 8 1 9 *"` (September 1 only). The PR description called it "weekly" but the intent is clearly a pre-season annual run. Fix: rename to make the yearly intent explicit, update the comment.

**Files:**
- Modify: `.github/workflows/scrape-platform-data.yml`

- [ ] **Step 1: Update workflow name and cron comment**

```yaml
name: Ingest Platform Data — Pre-Season Annual (Sep 1)

on:
  schedule:
    - cron: "0 8 1 9 *"  # Sep 1 8am UTC — runs once per year before the season
  workflow_dispatch:
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/scrape-platform-data.yml
git commit -m "fix(ci): clarify pre-season workflow name and cron comment

Rename from misleading 'Ingest Platform Data' to explicitly note this
runs once per year on September 1 (not weekly as the PR description said).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Fix token mutation in tests — use `monkeypatch`

Both `test_yahoo.py::test_skips_when_no_oauth_token` and `test_fantrax.py::test_skips_when_no_session_token` mutate the global `settings` singleton with `try/finally`. Replace with `monkeypatch.setattr` which handles cleanup automatically and is safe under parallel test execution.

**Files:**
- Modify: `apps/api/tests/scrapers/projection/test_yahoo.py`
- Modify: `apps/api/tests/scrapers/projection/test_fantrax.py`

- [ ] **Step 1: Update `test_yahoo.py`**

Replace:

```python
async def test_skips_when_no_oauth_token(self) -> None:
    from core.config import settings
    original = settings.yahoo_oauth_refresh_token
    settings.yahoo_oauth_refresh_token = ""
    try:
        mock_db = MagicMock()
        count = await YahooScraper().scrape("2025-26", mock_db)
        assert count == 0
    finally:
        settings.yahoo_oauth_refresh_token = original
```

With:

```python
    @pytest.mark.asyncio
    async def test_skips_when_no_oauth_token(self, monkeypatch) -> None:
        monkeypatch.setattr("core.config.settings.yahoo_oauth_refresh_token", "")
        mock_db = MagicMock()
        count = await YahooScraper().scrape("2025-26", mock_db)
        assert count == 0
```

- [ ] **Step 2: Update `test_fantrax.py`**

Replace:

```python
    @pytest.mark.asyncio
    async def test_skips_when_no_session_token(self) -> None:
        from core.config import settings
        original = settings.fantrax_session_token
        settings.fantrax_session_token = ""
        try:
            mock_db = MagicMock()
            count = await FantraxScraper().scrape("2025-26", mock_db)
            assert count == 0
        finally:
            settings.fantrax_session_token = original
```

With:

```python
    @pytest.mark.asyncio
    async def test_skips_when_no_session_token(self, monkeypatch) -> None:
        monkeypatch.setattr("core.config.settings.fantrax_session_token", "")
        mock_db = MagicMock()
        count = await FantraxScraper().scrape("2025-26", mock_db)
        assert count == 0
```

- [ ] **Step 3: Run all scraper tests**

```bash
cd apps/api && pytest tests/scrapers/ -v
```

Expected: all green, ruff clean.

- [ ] **Step 4: Final ruff check**

```bash
cd apps/api && ruff check .
```

Expected: no issues.

- [ ] **Step 5: Commit**

```bash
git add apps/api/tests/scrapers/projection/test_yahoo.py \
        apps/api/tests/scrapers/projection/test_fantrax.py
git commit -m "fix(tests): use monkeypatch for settings mutation in Yahoo and Fantrax tests

Direct settings mutation is fragile under parallel test execution.
monkeypatch.setattr handles cleanup automatically and is pytest-idiomatic.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Final Verification

- [ ] Run the full test suite from the api root:

```bash
cd apps/api && pytest --tb=short
```

Expected: all tests green, coverage unchanged or improved.

- [ ] Push branch and verify CI passes:

```bash
git push origin feat/phase2-platform-scrapers
```

- [ ] Update PR description to note all review issues addressed.
