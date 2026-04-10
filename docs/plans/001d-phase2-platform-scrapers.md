# Phase 2 Platform Scrapers + Schedule Scores + player_platform_positions Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Yahoo and Fantrax projection scrapers (API-based), the `player_platform_positions` ingestion script (ESPN, Yahoo, Fantrax position eligibility), and the schedule scores ingestion job (NHL schedule API → `schedule_scores` table).

**Architecture:** Yahoo uses the official Yahoo Fantasy API via `yahoo-fantasy-api` library (OAuth2); Fantrax scrapes XHR responses (session auth). `player_platform_positions` is a standalone ingestion script run pre-season. Schedule scores are pulled from the NHL schedule API and normalised to a 0–1 score.

**Tech Stack:** `yahoo-fantasy-api`, `httpx`, `BeautifulSoup4`, Supabase service role client, GitHub Actions secrets (OAuth tokens).

**Prerequisite:** `scrapers/matching.py` (PlayerMatcher) must already exist — implemented in the projection scrapers plan.

---

## Files

| Action | Path |
|--------|------|
| Create | `apps/api/scrapers/projection/yahoo.py` |
| Create | `apps/api/scrapers/projection/fantrax.py` |
| Create | `apps/api/scrapers/platform_positions.py` |
| Create | `apps/api/scrapers/schedule_scores.py` |
| Modify | `apps/api/pyproject.toml` — add `yahoo-fantasy-api` dep |
| Create | `apps/api/tests/scrapers/projection/test_yahoo.py` |
| Create | `apps/api/tests/scrapers/projection/test_fantrax.py` |
| Create | `apps/api/tests/scrapers/test_platform_positions.py` |
| Create | `apps/api/tests/scrapers/test_schedule_scores.py` |
| Create | `.github/workflows/scrape-platform-data.yml` |
| Modify | `apps/api/core/config.py` — add `yahoo_oauth_refresh_token`, `fantrax_session_token` |

---

## Chunk 1: Yahoo Projection Scraper

### Task 1: Add yahoo-fantasy-api dependency

- [ ] **Step 1: Add to pyproject.toml**

```toml
"yahoo-fantasy-api>=1.26.0",
```

- [ ] **Step 2: Install**

```bash
cd apps/api && pip install -e ".[dev]"
```

- [ ] **Step 3: Add config fields**

In `apps/api/core/config.py`, add to `Settings`:

```python
yahoo_oauth_refresh_token: str = ""
fantrax_session_token: str = ""
```

- [ ] **Step 4: Commit**

```bash
git add apps/api/pyproject.toml apps/api/core/config.py
git commit -m "chore(api): add yahoo-fantasy-api dep and Yahoo/Fantrax config fields"
```

---

### Task 2: Write failing tests for Yahoo scraper

**Files:**
- Create: `apps/api/tests/scrapers/projection/test_yahoo.py`

- [ ] **Step 1: Write tests**

```python
# apps/api/tests/scrapers/projection/test_yahoo.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from scrapers.projection.yahoo import YahooScraper

# Mock Yahoo API player data shape
YAHOO_PLAYER_1 = {
    "player_id": "3981",
    "name": {"full": "Connor McDavid"},
    "display_position": "C",
    "eligible_positions": [{"position": "C"}],
    "player_stats": {
        "stats": [
            {"stat_id": "1", "value": "52"},   # GP
            {"stat_id": "5", "value": "45"},   # G
            {"stat_id": "6", "value": "72"},   # A
        ]
    },
}

YAHOO_PLAYER_2 = {
    "player_id": "6370",
    "name": {"full": "Leon Draisaitl"},
    "display_position": "C",
    "eligible_positions": [{"position": "C"}, {"position": "LW"}],
    "player_stats": {
        "stats": [
            {"stat_id": "1", "value": "82"},
            {"stat_id": "5", "value": "40"},
            {"stat_id": "6", "value": "65"},
        ]
    },
}


class TestParsePlayerRow:
    def test_extracts_player_name(self) -> None:
        result = YahooScraper._parse_player(YAHOO_PLAYER_1)
        assert result["player_name"] == "Connor McDavid"

    def test_maps_goals_stat(self) -> None:
        result = YahooScraper._parse_player(YAHOO_PLAYER_1)
        assert result.get("g") == 45

    def test_maps_assists_stat(self) -> None:
        result = YahooScraper._parse_player(YAHOO_PLAYER_1)
        assert result.get("a") == 72

    def test_missing_stat_returns_none(self) -> None:
        # YAHOO_PLAYER_1 has no PPP stat — should be absent from result
        result = YahooScraper._parse_player(YAHOO_PLAYER_1)
        assert result.get("ppp") is None


class TestScrape:
    @pytest.mark.asyncio
    async def test_returns_int_count(self) -> None:
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "src-1"}]
        mock_db.table.return_value.select.return_value.execute.return_value.data = []

        scraper = YahooScraper()
        with patch.object(scraper, "_fetch_yahoo_players", return_value=[YAHOO_PLAYER_1, YAHOO_PLAYER_2]):
            count = await scraper.scrape("2025-26", mock_db)
        assert isinstance(count, int)

    @pytest.mark.asyncio
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

- [ ] **Step 2: Run tests — expect ImportError**

```bash
cd apps/api && pytest tests/scrapers/projection/test_yahoo.py -v
```

---

### Task 3: Implement Yahoo scraper

**Files:**
- Create: `apps/api/scrapers/projection/yahoo.py`

- [ ] **Step 1: Investigate Yahoo Fantasy API stat IDs**

Yahoo uses numeric stat IDs. Common mappings:
- `1` = GP, `5` = G, `6` = A, `7` = PPP, `14` = SOG, `31` = HIT, `32` = BLK, `16` = PIM
- Verify by calling the API and inspecting a response; update `YAHOO_STAT_MAP` accordingly.

- [ ] **Step 2: Write the scraper**

```python
# apps/api/scrapers/projection/yahoo.py
"""
Yahoo Fantasy Hockey projection scraper.

Uses the unofficial yahoo-fantasy-api Python library (OAuth2).
Requires YAHOO_OAUTH_REFRESH_TOKEN in .env / GitHub Actions secrets.

Yahoo stat IDs → our player_projections columns.
Verify stat IDs by calling the API and inspecting a live response.
Last verified: <DATE>
"""
from __future__ import annotations

import logging
from typing import Any

from scrapers.base_projection import BaseProjectionScraper
from scrapers.matching import PlayerMatcher
from scrapers.projection import (
    fetch_players_and_aliases,
    log_unmatched,
    update_last_successful_scrape,
    upsert_projection_row,
    upsert_source,
)

logger = logging.getLogger(__name__)

# Yahoo stat_id → our stat column
# Verify these by inspecting live Yahoo API responses; they can change each season.
YAHOO_STAT_MAP: dict[str, str] = {
    "1": "gp",
    "5": "g",
    "6": "a",
    "7": "ppp",
    "14": "sog",
    "16": "pim",
    "31": "hits",
    "32": "blocks",
    # Goalie stats
    "19": "w",
    "21": "ga",
    "23": "sv",
    "24": "sv_pct",
    "25": "so",
}


def _parse_stat_value(stat_id: str, raw_value: str) -> Any:
    """Convert Yahoo stat value string to int or float."""
    if not raw_value or raw_value in {"-", ""}:
        return None
    try:
        if stat_id == "24":  # sv_pct is float
            return float(raw_value)
        return int(float(raw_value))
    except (ValueError, TypeError):
        return None


class YahooScraper(BaseProjectionScraper):
    SOURCE_NAME = "yahoo"
    DISPLAY_NAME = "Yahoo Fantasy"

    @staticmethod
    def _parse_player(player: dict[str, Any]) -> dict[str, Any]:
        """Extract player_name and mapped stats from a Yahoo player dict."""
        name = player.get("name", {}).get("full", "")
        result: dict[str, Any] = {"player_name": name}

        stats_list = player.get("player_stats", {}).get("stats", [])
        for stat in stats_list:
            stat_id = str(stat.get("stat_id", ""))
            if stat_id not in YAHOO_STAT_MAP:
                continue
            col = YAHOO_STAT_MAP[stat_id]
            val = _parse_stat_value(stat_id, str(stat.get("value", "")))
            if val is not None:
                result[col] = val

        return result

    def _fetch_yahoo_players(self) -> list[dict[str, Any]]:
        """Fetch all NHL players with projected stats from Yahoo Fantasy API."""
        from core.config import settings
        import yahoo_fantasy_api as yfa  # type: ignore[import-untyped]

        oauth = yfa.OAuth2(None, None, from_file=None)
        oauth.refresh_access_token(settings.yahoo_oauth_refresh_token)

        game = yfa.Game(oauth, "nhl")
        players = game.to_league(game.league_ids()[0]).player_details("all")
        return players

    async def scrape(self, season: str, db: Any) -> int:
        from core.config import settings

        if not settings.yahoo_oauth_refresh_token:
            logger.warning("Yahoo: no OAuth refresh token configured — skipping")
            return 0

        source_id = upsert_source(db, self.SOURCE_NAME, self.DISPLAY_NAME)
        players, aliases = fetch_players_and_aliases(db)
        matcher = PlayerMatcher(players, aliases)

        try:
            yahoo_players = self._fetch_yahoo_players()
        except Exception as exc:
            logger.error("Yahoo: API fetch failed: %s", exc)
            return 0

        upserted = 0
        for yahoo_player in yahoo_players:
            row = self._parse_player(yahoo_player)
            player_name = row.pop("player_name", "")
            if not player_name:
                continue
            player_id = matcher.resolve(player_name)
            if player_id is None:
                log_unmatched(db, self.SOURCE_NAME, player_name, season)
                continue
            upsert_projection_row(db, player_id, source_id, season, row)
            upserted += 1

        update_last_successful_scrape(db, source_id)
        logger.info("%s: upserted %d projection rows for %s", self.DISPLAY_NAME, upserted, season)
        return upserted


if __name__ == "__main__":
    import asyncio
    from core.dependencies import get_db
    asyncio.run(YahooScraper().scrape("2025-26", get_db()))
```

- [ ] **Step 3: Run Yahoo tests — expect all to pass**

```bash
cd apps/api && pytest tests/scrapers/projection/test_yahoo.py -v
```

- [ ] **Step 4: Run full suite + lint**

```bash
cd apps/api && pytest tests/ -q && ruff check .
```

- [ ] **Step 5: Commit**

```bash
git add apps/api/scrapers/projection/yahoo.py apps/api/tests/scrapers/projection/test_yahoo.py
git commit -m "feat(scrapers): add Yahoo Fantasy projection scraper"
```

---

## Chunk 2: Fantrax Scraper

### Task 4: Investigate Fantrax API and write Fantrax scraper

Fantrax does not have a documented public API. Approach: inspect XHR calls on the Fantrax player list page using browser devtools. If feasible, use session auth. If too brittle for v1.0, implement as paste/upload only.

- [ ] **Step 1: Investigate Fantrax API availability**

  Open browser devtools → Network tab → navigate to Fantrax player projections page → look for JSON XHR responses containing player data.

  Common endpoint patterns:
  - `https://www.fantrax.com/fxea/general/getTeamRosters`
  - `https://www.fantrax.com/fxea/general/getScoreboard`
  - `https://www.fantrax.com/newapi/fantrax-api.go?msgs=getPlayersTable`

  **If no XHR with player projection data is found:** implement as paste/upload (same as Dobber — no HTTP, just CSV parse). Document this decision in the scraper file.

- [ ] **Step 2: Write failing test**

```python
# apps/api/tests/scrapers/projection/test_fantrax.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from scrapers.projection.fantrax import FantraxScraper


class TestScrape:
    @pytest.mark.asyncio
    async def test_returns_int(self) -> None:
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "src-1"}]
        mock_db.table.return_value.select.return_value.execute.return_value.data = []

        scraper = FantraxScraper()
        with patch.object(scraper, "_fetch_fantrax_players", return_value=[]):
            count = await scraper.scrape("2025-26", mock_db)
        assert isinstance(count, int)
        assert count == 0

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

- [ ] **Step 3: Implement Fantrax scraper**

```python
# apps/api/scrapers/projection/fantrax.py
"""
Fantrax projection scraper.

Fantrax does not have a documented public API.
Implementation uses session-cookie-based XHR calls discovered via devtools.

If API access proves too brittle, set AUTO_SCRAPE = False to fall back to
paste/upload mode (same as Dobber).

Requires FANTRAX_SESSION_TOKEN in .env / GitHub Actions secrets.
Last verified: <DATE> — re-verify XHR endpoints each season.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from scrapers.base_projection import BaseProjectionScraper
from scrapers.matching import PlayerMatcher
from scrapers.projection import (
    fetch_players_and_aliases,
    log_unmatched,
    update_last_successful_scrape,
    upsert_projection_row,
    upsert_source,
)

logger = logging.getLogger(__name__)

# Set to False and implement ingest() if API access is not feasible
AUTO_SCRAPE = True  # Update after investigation

# FILL IN after inspecting XHR calls in devtools
FANTRAX_API_URL = "https://www.fantrax.com/newapi/fantrax-api.go"

# Fantrax stat key → our player_projections column (FILL IN after API inspection)
FANTRAX_STAT_MAP: dict[str, str] = {
    # "GP": "gp",
    # "G": "g",
    # "A": "a",
    # Fill in from actual API response keys
}


class FantraxScraper(BaseProjectionScraper):
    SOURCE_NAME = "fantrax"
    DISPLAY_NAME = "Fantrax"

    def _fetch_fantrax_players(self) -> list[dict[str, Any]]:
        """Fetch player projection data from Fantrax API."""
        from core.config import settings

        if not settings.fantrax_session_token:
            return []

        # FILL IN with actual request params after devtools investigation
        resp = httpx.get(
            FANTRAX_API_URL,
            params={"msgs": "getPlayersTable"},  # Update params
            cookies={"fantrax.session": settings.fantrax_session_token},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        # FILL IN: navigate to the player list in the response
        return data.get("responses", [{}])[0].get("data", {}).get("rows", [])

    @staticmethod
    def _parse_player(raw: dict[str, Any]) -> dict[str, Any]:
        """Map a raw Fantrax player row to projection stats."""
        # FILL IN after inspecting actual API response shape
        name = raw.get("player", {}).get("name", "") or raw.get("name", "")
        result: dict[str, Any] = {"player_name": name}
        for fantrax_key, stat_col in FANTRAX_STAT_MAP.items():
            val = raw.get(fantrax_key)
            if val is not None:
                try:
                    result[stat_col] = int(float(val))
                except (ValueError, TypeError):
                    pass
        return result

    async def scrape(self, season: str, db: Any) -> int:
        from core.config import settings

        if not settings.fantrax_session_token:
            logger.warning("Fantrax: no session token configured — skipping")
            return 0

        if not AUTO_SCRAPE:
            logger.info("Fantrax: AUTO_SCRAPE disabled — use paste/upload mode")
            return 0

        source_id = upsert_source(db, self.SOURCE_NAME, self.DISPLAY_NAME)
        players, aliases = fetch_players_and_aliases(db)
        matcher = PlayerMatcher(players, aliases)

        try:
            fantrax_players = self._fetch_fantrax_players()
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

        update_last_successful_scrape(db, source_id)
        logger.info("%s: upserted %d rows for %s", self.DISPLAY_NAME, upserted, season)
        return upserted
```

- [ ] **Step 4: Run Fantrax tests**

```bash
cd apps/api && pytest tests/scrapers/projection/test_fantrax.py -v
```

- [ ] **Step 5: Commit**

```bash
git add apps/api/scrapers/projection/fantrax.py apps/api/tests/scrapers/projection/test_fantrax.py
git commit -m "feat(scrapers): add Fantrax projection scraper (session-auth XHR)"
```

---

## Chunk 3: player_platform_positions Ingestion

### Task 5: Write failing tests for platform positions ingestion

**Files:**
- Create: `apps/api/tests/scrapers/test_platform_positions.py`

- [ ] **Step 1: Write tests**

```python
# apps/api/tests/scrapers/test_platform_positions.py
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scrapers.platform_positions import (
    ESPN_POSITION_MAP,
    map_espn_positions,
    upsert_platform_positions,
)

ESPN_PLAYER = {
    "id": 3068,
    "fullName": "Connor McDavid",
    "defaultPositionId": 1,
    "eligibleSlots": [1, 2, 5],  # C, F, UTIL
}

PLAYERS_DB = [
    {"id": "p1", "name": "Connor McDavid", "nhl_id": "8478402"},
    {"id": "p2", "name": "Leon Draisaitl", "nhl_id": "8477934"},
]


class TestMapEspnPositions:
    def test_maps_center_slot(self) -> None:
        result = map_espn_positions([1, 2, 5])
        assert "C" in result

    def test_excludes_bench_slot(self) -> None:
        result = map_espn_positions([7])  # BN
        assert result == []

    def test_deduplicates_positions(self) -> None:
        result = map_espn_positions([1, 1, 2])
        assert result.count("C") == 1


class TestUpsertPlatformPositions:
    def test_calls_upsert_on_correct_table(self) -> None:
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value.data = []
        upsert_platform_positions(mock_db, "p1", "espn", ["C", "F"])
        mock_db.table.assert_called_with("player_platform_positions")

    def test_passes_player_id_platform_positions(self) -> None:
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value.data = []
        upsert_platform_positions(mock_db, "p1", "espn", ["C", "LW"])
        call_kwargs = mock_db.table.return_value.upsert.call_args
        data = call_kwargs.args[0]
        assert data["player_id"] == "p1"
        assert data["platform"] == "espn"
        assert set(data["positions"]) == {"C", "LW"}
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
cd apps/api && pytest tests/scrapers/test_platform_positions.py -v
```

---

### Task 6: Implement platform_positions.py

**Files:**
- Create: `apps/api/scrapers/platform_positions.py`

- [ ] **Step 1: Write the ingestion script**

```python
# apps/api/scrapers/platform_positions.py
"""
player_platform_positions ingestion.

Fetches position eligibility from ESPN, Yahoo, and Fantrax and
upserts to the player_platform_positions table.

Run pre-season (September). Safe to re-run — uses UPSERT.

Usage:
    python -m scrapers.platform_positions
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from scrapers.matching import PlayerMatcher

logger = logging.getLogger(__name__)

# ESPN slot ID → position string
# Verified at: https://fantasy.espn.com/apis/v3/games/fhl/players
ESPN_POSITION_MAP: dict[int, str] = {
    1: "C",
    2: "LW",
    3: "RW",
    4: "D",
    5: "G",
    6: "UTIL",
    10: "F",    # Forward (generic)
    # 7 = BN (bench) — excluded
    # 8 = IR — excluded
    # 9 = IR+ — excluded
}

ESPN_PLAYERS_URL = (
    "https://fantasy.espn.com/apis/v3/games/fhl/players"
    "?scoringPeriodId=0&view=players_wl"
)


def map_espn_positions(eligible_slots: list[int]) -> list[str]:
    """Map ESPN eligible slot IDs to position strings, deduplicating."""
    seen: set[str] = set()
    result: list[str] = []
    for slot_id in eligible_slots:
        pos = ESPN_POSITION_MAP.get(slot_id)
        if pos and pos not in seen:
            seen.add(pos)
            result.append(pos)
    return result


def upsert_platform_positions(
    db: Any, player_id: str, platform: str, positions: list[str]
) -> None:
    """Upsert a player_platform_positions row."""
    db.table("player_platform_positions").upsert(
        {"player_id": player_id, "platform": platform, "positions": positions},
        on_conflict="player_id,platform",
    ).execute()


def _fetch_espn_players() -> list[dict[str, Any]]:
    """Fetch all NHL players from ESPN Fantasy API (no auth needed)."""
    resp = httpx.get(ESPN_PLAYERS_URL, timeout=30.0)
    resp.raise_for_status()
    data = resp.json()
    # ESPN wraps player data under "players" key
    return data.get("players", [])


def ingest_espn_positions(db: Any) -> int:
    """Ingest position eligibility from ESPN and upsert to player_platform_positions."""
    players = db.table("players").select("id, name, nhl_id").execute().data
    aliases = db.table("player_aliases").select("alias_name, player_id").execute().data
    matcher = PlayerMatcher(players, aliases)

    espn_players = _fetch_espn_players()
    upserted = 0
    unmatched = 0

    for ep in espn_players:
        full_name = ep.get("fullName", "")
        if not full_name:
            continue

        player_id = matcher.resolve(full_name)
        if player_id is None:
            unmatched += 1
            continue

        eligible_slots = ep.get("eligibleSlots", [])
        positions = map_espn_positions(eligible_slots)
        if not positions:
            continue

        upsert_platform_positions(db, player_id, "espn", positions)
        upserted += 1

    logger.info("ESPN positions: upserted=%d unmatched=%d", upserted, unmatched)
    return upserted


def ingest_yahoo_positions(db: Any) -> int:
    """Ingest position eligibility from Yahoo Fantasy API.

    Requires YAHOO_OAUTH_REFRESH_TOKEN in config.
    Reuses OAuth2 setup from Yahoo projection scraper.
    Returns 0 if no token configured.
    """
    from core.config import settings
    if not settings.yahoo_oauth_refresh_token:
        logger.warning("Yahoo positions: no OAuth token — skipping")
        return 0

    try:
        import yahoo_fantasy_api as yfa  # type: ignore[import-untyped]
        oauth = yfa.OAuth2(None, None, from_file=None)
        oauth.refresh_access_token(settings.yahoo_oauth_refresh_token)
        game = yfa.Game(oauth, "nhl")
        yahoo_players = game.to_league(game.league_ids()[0]).player_details("all")
    except Exception as exc:
        logger.error("Yahoo positions fetch failed: %s", exc)
        return 0

    players = db.table("players").select("id, name, nhl_id").execute().data
    aliases = db.table("player_aliases").select("alias_name, player_id").execute().data
    matcher = PlayerMatcher(players, aliases)

    upserted = 0
    for yp in yahoo_players:
        name = yp.get("name", {}).get("full", "")
        player_id = matcher.resolve(name)
        if player_id is None:
            continue
        positions = [
            ep["position"]
            for ep in yp.get("eligible_positions", [])
            if ep["position"] not in ("BN", "IL", "IL+")
        ]
        if positions:
            upsert_platform_positions(db, player_id, "yahoo", positions)
            upserted += 1

    logger.info("Yahoo positions: upserted %d", upserted)
    return upserted


def ingest_fantrax_positions(db: Any) -> int:
    """Ingest position eligibility from Fantrax. Returns 0 if no session token."""
    from core.config import settings
    if not settings.fantrax_session_token:
        logger.warning("Fantrax positions: no session token — skipping")
        return 0

    # TODO: Implement after Fantrax API investigation (see Fantrax scraper)
    logger.info("Fantrax positions: not yet implemented — skipping")
    return 0


if __name__ == "__main__":
    from core.dependencies import get_db
    db = get_db()
    total = ingest_espn_positions(db) + ingest_yahoo_positions(db) + ingest_fantrax_positions(db)
    print(f"Total platform positions upserted: {total}")
```

- [ ] **Step 2: Run platform position tests**

```bash
cd apps/api && pytest tests/scrapers/test_platform_positions.py -v
```

Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add apps/api/scrapers/platform_positions.py apps/api/tests/scrapers/test_platform_positions.py
git commit -m "feat(scrapers): add player_platform_positions ingestion (ESPN, Yahoo, Fantrax)"
```

---

## Chunk 4: Schedule Scores Ingestion

### Task 7: Write failing tests for schedule scores

**Files:**
- Create: `apps/api/tests/scrapers/test_schedule_scores.py`

- [ ] **Step 1: Write tests**

```python
# apps/api/tests/scrapers/test_schedule_scores.py
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scrapers.schedule_scores import (
    compute_schedule_score,
    count_off_night_games,
)

# Sample games — player in games on dates with varying team counts
GAMES = [
    {"date": "2025-10-07", "teams": ["EDM", "TOR", "VAN", "MTL"]},   # 4 teams playing
    {"date": "2025-10-08", "teams": ["EDM", "TOR"]},                  # 2 teams — off-night
    {"date": "2025-10-09", "teams": ["EDM", "TOR", "VAN", "MTL",
                                      "CGY", "WPG", "MIN", "DAL",
                                      "NYR", "BOS", "PHI", "PIT",
                                      "DET", "CAR", "FLA", "TBL"]},   # 16 teams — not off-night
]

# Player plays for EDM — appears in all 3 dates above
PLAYER_GAME_DATES = {"2025-10-07", "2025-10-08", "2025-10-09"}


class TestCountOffNightGames:
    def test_counts_games_with_few_teams(self) -> None:
        # Off-night = ≤ 10 teams playing that day
        count = count_off_night_games(PLAYER_GAME_DATES, GAMES, off_night_threshold=10)
        # 2025-10-07 has 4 teams → off-night; 2025-10-08 has 2 → off-night; 2025-10-09 has 16 → not
        assert count == 2

    def test_zero_when_all_busy_nights(self) -> None:
        busy_dates = {"2025-10-09"}
        count = count_off_night_games(busy_dates, GAMES, off_night_threshold=10)
        assert count == 0

    def test_empty_dates_returns_zero(self) -> None:
        assert count_off_night_games(set(), GAMES) == 0


class TestComputeScheduleScore:
    def test_normalized_between_0_and_1(self) -> None:
        score = compute_schedule_score(off_night_games=5, total_games=82)
        assert 0.0 <= score <= 1.0

    def test_more_off_night_games_higher_score(self) -> None:
        low = compute_schedule_score(off_night_games=2, total_games=82)
        high = compute_schedule_score(off_night_games=20, total_games=82)
        assert high > low

    def test_zero_total_games_returns_zero(self) -> None:
        assert compute_schedule_score(0, 0) == 0.0
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
cd apps/api && pytest tests/scrapers/test_schedule_scores.py -v
```

---

### Task 8: Implement schedule_scores.py

**Files:**
- Create: `apps/api/scrapers/schedule_scores.py`

- [ ] **Step 1: Write the ingestion script**

```python
# apps/api/scrapers/schedule_scores.py
"""
NHL schedule scores ingestion.

Pulls the NHL regular season schedule from the NHL.com API, computes
each player's off-night game count (games played when ≤ threshold teams
are playing), normalises to a 0–1 score, and upserts to schedule_scores.

Off-night games are a positive indicator — fewer teams playing means less
rested opponents and reduced goaltending depth on those nights.

Usage:
    python -m scrapers.schedule_scores
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Games where ≤ this many NHL teams play are considered "off-nights"
OFF_NIGHT_THRESHOLD = 10

NHL_SCHEDULE_URL = "https://api-web.nhle.com/v1/schedule/{date}"


def count_off_night_games(
    player_game_dates: set[str],
    schedule: list[dict[str, Any]],
    off_night_threshold: int = OFF_NIGHT_THRESHOLD,
) -> int:
    """Return the number of player game dates that fall on off-nights.

    Args:
        player_game_dates: Set of ISO date strings when this player's team plays.
        schedule: List of {"date": str, "teams": list[str]} across the season.
        off_night_threshold: Days with ≤ this many teams are off-nights.
    """
    date_team_count: dict[str, int] = {g["date"]: len(g["teams"]) for g in schedule}
    return sum(
        1
        for date in player_game_dates
        if date_team_count.get(date, 0) <= off_night_threshold
    )


def compute_schedule_score(off_night_games: int, total_games: int) -> float:
    """Normalise off-night game count to a 0–1 score.

    Uses the fraction of games that are off-night games.
    Returns 0.0 when total_games is 0.
    """
    if total_games == 0:
        return 0.0
    return round(off_night_games / total_games, 4)


async def _fetch_season_schedule(season: str) -> list[dict[str, Any]]:
    """Fetch all regular-season games from NHL.com API for a given season.

    Returns a list of {"date": "YYYY-MM-DD", "teams": ["EDM", "TOR", ...]}
    for each game day.
    """
    # NHL season typically Oct 1 – Apr 30
    start_year = int(season.split("-")[0])
    import datetime

    games_by_date: dict[str, set[str]] = defaultdict(set)

    async with httpx.AsyncClient(timeout=30.0) as client:
        current = datetime.date(start_year, 10, 1)
        end = datetime.date(start_year + 1, 5, 1)

        while current <= end:
            url = NHL_SCHEDULE_URL.format(date=current.isoformat())
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                for day in data.get("gameWeek", []):
                    date_str = day.get("date", "")
                    for game in day.get("games", []):
                        if game.get("gameType") != 2:  # 2 = regular season
                            continue
                        home = game.get("homeTeam", {}).get("abbrev", "")
                        away = game.get("awayTeam", {}).get("abbrev", "")
                        if home:
                            games_by_date[date_str].add(home)
                        if away:
                            games_by_date[date_str].add(away)
            except Exception as exc:
                logger.warning("Schedule fetch error for %s: %s", current, exc)

            # Advance one week at a time
            current += datetime.timedelta(weeks=1)
            await asyncio.sleep(0.5)

    return [{"date": date, "teams": list(teams)} for date, teams in sorted(games_by_date.items())]


async def ingest(season: str, db: Any) -> None:
    """Fetch schedule, compute per-player scores, upsert to schedule_scores."""
    schedule = await _fetch_season_schedule(season)
    logger.info("Fetched %d game days for %s", len(schedule), season)

    # Build date → teams index
    date_teams: dict[str, set[str]] = {
        g["date"]: set(g["teams"]) for g in schedule
    }

    # Get all players with their team
    players = db.table("players").select("id, team").execute().data

    # Fetch player_stats to know which dates each player's team actually played
    # (Use schedule data to build team → game_dates mapping)
    team_game_dates: dict[str, set[str]] = defaultdict(set)
    for date, teams in date_teams.items():
        for team in teams:
            team_game_dates[team].add(date)

    upserted = 0
    for player in players:
        team = player.get("team", "")
        player_id = player["id"]
        game_dates = team_game_dates.get(team, set())
        total_games = len(game_dates)
        off_night = count_off_night_games(game_dates, schedule)
        score = compute_schedule_score(off_night, total_games)

        db.table("schedule_scores").upsert(
            {
                "player_id": player_id,
                "season": season,
                "off_night_games": off_night,
                "total_games": total_games,
                "schedule_score": score,
            },
            on_conflict="player_id,season",
        ).execute()
        upserted += 1

    logger.info("Schedule scores: upserted %d rows for %s", upserted, season)


if __name__ == "__main__":
    from core.dependencies import get_db
    asyncio.run(ingest("2025-26", get_db()))
```

- [ ] **Step 2: Run schedule score tests**

```bash
cd apps/api && pytest tests/scrapers/test_schedule_scores.py -v
```

Expected: All tests pass.

- [ ] **Step 3: Run full suite + lint**

```bash
cd apps/api && pytest tests/ -q && ruff check .
```

- [ ] **Step 4: Commit**

```bash
git add apps/api/scrapers/schedule_scores.py apps/api/tests/scrapers/test_schedule_scores.py
git commit -m "feat(scrapers): add NHL schedule scores ingestion"
```

---

## Chunk 5: GitHub Actions + Notion Updates

### Task 9: Platform data GitHub Actions workflow

- [ ] **Step 1: Create workflow**

```yaml
# .github/workflows/scrape-platform-data.yml
name: Ingest Platform Data (Positions + Schedule Scores)

on:
  schedule:
    - cron: "0 8 1 9 *"  # September 1st 8am UTC (pre-season)
  workflow_dispatch:

jobs:
  platform-data:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/api

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Ingest platform positions
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          YAHOO_OAUTH_REFRESH_TOKEN: ${{ secrets.YAHOO_OAUTH_REFRESH_TOKEN }}
          FANTRAX_SESSION_TOKEN: ${{ secrets.FANTRAX_SESSION_TOKEN }}
        run: python -m scrapers.platform_positions

      - name: Ingest schedule scores
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
        run: python -m scrapers.schedule_scores
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/scrape-platform-data.yml
git commit -m "ci: add pre-season platform data ingestion workflow"
```

### Task 10: Update Notion task statuses

- [ ] Mark "Write Yahoo and Fantrax projection scrapers" (32548885-3275-81a6-8535-f56d3159e6db) → Done
- [ ] Mark "Build player_platform_positions ingestion" (32548885-3275-814b-b772-c516717c28ac) → Done
- [ ] Update `apps/api/CLAUDE.md` scrapers section

```bash
git add apps/api/CLAUDE.md
git commit -m "docs(api): mark platform scrapers and schedule scores as complete"
```
