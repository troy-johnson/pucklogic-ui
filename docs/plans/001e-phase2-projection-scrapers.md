# Phase 2 Projection Scrapers Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `scrapers/matching.py` (rapidfuzz player name resolution shared by all scrapers) and five HTML projection scrapers: HashtagHockey, DailyFaceoff, Dobber (paste/upload only — paywalled), Apples & Ginos, and LineupExperts. Also includes NST stats scraper (`scrapers/nst.py`).

**Architecture:** Each projection scraper subclasses `BaseProjectionScraper` (and `BaseScraper` for HTTP) and delegates player name resolution to `matching.resolve_player`. The matching module checks exact match → `player_aliases` → rapidfuzz. Dobber is paywalled — implemented as a CSV parse-only scraper (no HTTP; users upload the file). Scrapers are invoked by GitHub Actions cron and can be triggered manually via `python -m scrapers.projection.<name>`.

**Tech Stack:** `rapidfuzz`, `httpx`, `BeautifulSoup4` (for HTML scrapers), `pandas` (CSV parse for Dobber), `playwright` only if site is JS-rendered (check before adding dependency).

**Before coding any scraper:** Inspect the live site (or a saved HTML fixture) to confirm CSS selectors, table structure, and whether it is JS-rendered. Document findings in a comment at the top of each scraper file.

---

## Files

| Action | Path |
|--------|------|
| Create | `apps/api/scrapers/matching.py` |
| Create | `apps/api/scrapers/projection/__init__.py` |
| Create | `apps/api/scrapers/projection/hashtag_hockey.py` |
| Create | `apps/api/scrapers/projection/daily_faceoff.py` |
| Create | `apps/api/scrapers/projection/dobber.py` |
| Create | `apps/api/scrapers/projection/apples_ginos.py` |
| Create | `apps/api/scrapers/projection/lineup_experts.py` |
| Create | `apps/api/scrapers/nst.py` |
| Modify | `apps/api/pyproject.toml` — add `rapidfuzz`, `beautifulsoup4`, `lxml`, `pandas` deps if not present |
| Create | `apps/api/tests/scrapers/test_matching.py` |
| Create | `apps/api/tests/scrapers/projection/test_hashtag_hockey.py` |
| Create | `apps/api/tests/scrapers/projection/test_daily_faceoff.py` |
| Create | `apps/api/tests/scrapers/projection/test_dobber.py` |
| Create | `apps/api/tests/scrapers/projection/test_apples_ginos.py` |
| Create | `apps/api/tests/scrapers/projection/test_lineup_experts.py` |
| Create | `apps/api/tests/scrapers/test_nst.py` |
| Create | `apps/api/tests/scrapers/projection/__init__.py` |
| Create | `apps/api/tests/scrapers/fixtures/` — HTML snapshot fixtures (one per scraper) |
| Create | `.github/workflows/scrape-projections.yml` — cron for pre-season scraping |

---

## Chunk 1: Dependencies + Player Name Matching

### Task 1: Add missing dependencies to pyproject.toml

**Files:**
- Modify: `apps/api/pyproject.toml`

- [ ] **Step 1: Check existing deps**

```bash
cd apps/api && grep -E "rapidfuzz|beautifulsoup4|lxml|pandas" pyproject.toml
```

- [ ] **Step 2: Add any missing deps to `[project.dependencies]`**

```toml
"rapidfuzz>=3.10.0",
"beautifulsoup4>=4.12.0",
"lxml>=5.0.0",
"pandas>=2.0.0",
```

- [ ] **Step 3: Install**

```bash
cd apps/api && pip install -e ".[dev]"
```

- [ ] **Step 4: Commit**

```bash
git add apps/api/pyproject.toml
git commit -m "chore(api): add rapidfuzz, beautifulsoup4, lxml, pandas dependencies"
```

---

### Task 2: Write failing tests for matching.py

**Files:**
- Create: `apps/api/tests/scrapers/test_matching.py`

- [ ] **Step 1: Write the test file**

```python
# apps/api/tests/scrapers/test_matching.py
"""Unit tests for scrapers/matching.py — no DB, no HTTP."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from scrapers.matching import PlayerMatcher

PLAYERS = [
    {"id": "p1", "name": "Connor McDavid", "nhl_id": "8478402"},
    {"id": "p2", "name": "Leon Draisaitl", "nhl_id": "8477934"},
    {"id": "p3", "name": "Jesperi Kotkaniemi", "nhl_id": "8481522"},
    {"id": "p4", "name": "Nathan MacKinnon", "nhl_id": "8477492"},
]

ALIASES = [
    {"alias_name": "J. Kotkaniemi", "player_id": "p3", "source": "hashtag"},
    {"alias_name": "Mac Kinnon", "player_id": "p4", "source": "test"},
]


@pytest.fixture
def matcher() -> PlayerMatcher:
    return PlayerMatcher(players=PLAYERS, aliases=ALIASES)


class TestExactMatch:
    def test_exact_name_match(self, matcher: PlayerMatcher) -> None:
        assert matcher.resolve("Connor McDavid") == "p1"

    def test_case_insensitive(self, matcher: PlayerMatcher) -> None:
        assert matcher.resolve("connor mcdavid") == "p1"

    def test_strips_whitespace(self, matcher: PlayerMatcher) -> None:
        assert matcher.resolve("  Leon Draisaitl  ") == "p2"


class TestAliasMatch:
    def test_finds_via_alias(self, matcher: PlayerMatcher) -> None:
        assert matcher.resolve("J. Kotkaniemi") == "p3"

    def test_alias_case_insensitive(self, matcher: PlayerMatcher) -> None:
        assert matcher.resolve("j. kotkaniemi") == "p3"


class TestFuzzyMatch:
    def test_fuzzy_matches_close_name(self, matcher: PlayerMatcher) -> None:
        # "McDavid Connor" — transposed — should still match
        result = matcher.resolve("McDavid Connor")
        assert result == "p1"

    def test_returns_none_below_threshold(self, matcher: PlayerMatcher) -> None:
        assert matcher.resolve("Totally Unknown Player") is None

    def test_custom_threshold_strict(self, matcher: PlayerMatcher) -> None:
        # Very strict threshold — "McDavid Connor" should not match at 99
        result = matcher.resolve("McDavid Connor", threshold=99)
        assert result is None


class TestEdgeCases:
    def test_empty_name_returns_none(self, matcher: PlayerMatcher) -> None:
        assert matcher.resolve("") is None

    def test_empty_players_list(self) -> None:
        m = PlayerMatcher(players=[], aliases=[])
        assert m.resolve("Connor McDavid") is None
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
cd apps/api && pytest tests/scrapers/test_matching.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scrapers.matching'`

---

### Task 3: Implement scrapers/matching.py

**Files:**
- Create: `apps/api/scrapers/matching.py`

- [ ] **Step 1: Write the module**

```python
# apps/api/scrapers/matching.py
"""
Player name resolution for projection scrapers.

Uses a three-level lookup:
  1. Exact match (normalised to lowercase, stripped)
  2. player_aliases lookup (pre-seeded cross-source name variants)
  3. rapidfuzz token_sort_ratio fuzzy match against canonical player names

Usage:
    matcher = PlayerMatcher(players=db_players, aliases=db_aliases)
    player_id = matcher.resolve("J. Kotkaniemi")  # → UUID or None
"""
from __future__ import annotations

from typing import Any

from rapidfuzz import fuzz, process


class PlayerMatcher:
    def __init__(
        self,
        players: list[dict[str, Any]],
        aliases: list[dict[str, Any]],
    ) -> None:
        # Exact match index: normalised name → player_id
        self._exact: dict[str, str] = {
            p["name"].strip().lower(): p["id"] for p in players
        }
        # Alias index: normalised alias → player_id
        self._alias: dict[str, str] = {
            a["alias_name"].strip().lower(): a["player_id"] for a in aliases
        }
        # Fuzzy match corpus: list of canonical names in same order as _players
        self._players = players
        self._names: list[str] = [p["name"] for p in players]

    def resolve(self, raw_name: str, threshold: int = 85) -> str | None:
        """Resolve a raw player name string to a canonical player_id.

        Returns None if no match at or above ``threshold``.
        """
        if not raw_name or not raw_name.strip():
            return None

        normalised = raw_name.strip().lower()

        # 1. Exact
        if normalised in self._exact:
            return self._exact[normalised]

        # 2. Alias
        if normalised in self._alias:
            return self._alias[normalised]

        # 3. Fuzzy
        if not self._names:
            return None

        result = process.extractOne(
            raw_name,
            self._names,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=threshold,
        )
        if result is None:
            return None

        matched_name, _score, idx = result
        return self._players[idx]["id"]
```

- [ ] **Step 2: Run matching tests — expect all to pass**

```bash
cd apps/api && pytest tests/scrapers/test_matching.py -v
```

Expected: All tests pass.

- [ ] **Step 3: Run full suite**

```bash
cd apps/api && pytest tests/ -q
```

Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add apps/api/scrapers/matching.py apps/api/tests/scrapers/test_matching.py
git commit -m "feat(scrapers): add PlayerMatcher for rapidfuzz name resolution"
```

---

## Chunk 2: Shared Projection Scraper Helpers

### Task 4: Create scrapers/projection/__init__.py with shared helpers

**Files:**
- Create: `apps/api/scrapers/projection/__init__.py`

- [ ] **Step 1: Write shared helpers used by all projection scrapers**

```python
# apps/api/scrapers/projection/__init__.py
"""
Shared helpers for projection scrapers.

Each projection scraper calls these helpers rather than duplicating
DB interaction logic.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def upsert_source(db: Any, source_name: str, display_name: str) -> str:
    """Get or create a source row; return the source UUID."""
    result = (
        db.table("sources")
        .upsert(
            {"name": source_name, "display_name": display_name, "active": True},
            on_conflict="name",
        )
        .execute()
    )
    return result.data[0]["id"]


def fetch_players_and_aliases(db: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (players, aliases) for building a PlayerMatcher."""
    players = db.table("players").select("id, name, nhl_id").execute().data
    aliases = db.table("player_aliases").select("alias_name, player_id, source").execute().data
    return players, aliases


def upsert_projection_row(
    db: Any,
    player_id: str,
    source_id: str,
    season: str,
    stats: dict[str, Any],
) -> None:
    """Upsert a single player_projections row.

    ``stats`` should only contain non-None values — callers should strip
    None-valued keys before calling this function.
    """
    db.table("player_projections").upsert(
        {"player_id": player_id, "source_id": source_id, "season": season, **stats},
        on_conflict="player_id,source_id,season",
    ).execute()


def log_unmatched(db: Any, source_name: str, raw_name: str, season: str) -> None:
    """Insert a scraper_logs row for a player name that could not be matched."""
    try:
        db.table("scraper_logs").insert({
            "source": source_name,
            "event": "unmatched_player",
            "detail": f"season={season} raw_name={raw_name!r}",
        }).execute()
    except Exception as exc:
        logger.warning("Failed to log unmatched player %r: %s", raw_name, exc)


def update_last_successful_scrape(db: Any, source_id: str) -> None:
    """Stamp sources.last_successful_scrape = now() for this source."""
    db.table("sources").update(
        {"last_successful_scrape": "now()"}
    ).eq("id", source_id).execute()


def apply_column_map(
    raw_row: dict[str, str],
    column_map: dict[str, str],
) -> dict[str, Any]:
    """Map raw column headers to stat schema using column_map.

    Only maps columns present in column_map; everything else is dropped.
    Values that are empty strings, "-", or "N/A" are treated as None.
    """
    MISSING = {"", "-", "n/a", "na", "—"}
    result: dict[str, Any] = {}
    for raw_col, stat_key in column_map.items():
        val = raw_row.get(raw_col)
        if val is None:
            continue
        cleaned = str(val).strip().lower()
        if cleaned in MISSING:
            result[stat_key] = None
        else:
            try:
                # Most stats are integers; sv_pct is float
                result[stat_key] = float(val) if stat_key == "sv_pct" else int(float(val))
            except (ValueError, TypeError):
                result[stat_key] = None
    # Strip None values — null stat means "not projected"
    return {k: v for k, v in result.items() if v is not None}
```

- [ ] **Step 2: Create test init file**

```bash
mkdir -p apps/api/tests/scrapers/projection
touch apps/api/tests/scrapers/projection/__init__.py
mkdir -p apps/api/tests/scrapers/fixtures
```

- [ ] **Step 3: Write tests for shared helpers**

Create `apps/api/tests/scrapers/projection/test_helpers.py`:

```python
# apps/api/tests/scrapers/projection/test_helpers.py
from __future__ import annotations

from unittest.mock import MagicMock

from scrapers.projection import apply_column_map, upsert_source, fetch_players_and_aliases


class TestApplyColumnMap:
    COLUMN_MAP = {"Goals": "g", "Assists": "a", "PPP": "ppp", "SOG": "sog"}

    def test_maps_known_columns(self) -> None:
        raw = {"Goals": "30", "Assists": "40", "PPP": "20", "SOG": "200"}
        result = apply_column_map(raw, self.COLUMN_MAP)
        assert result == {"g": 30, "a": 40, "ppp": 20, "sog": 200}

    def test_ignores_unknown_columns(self) -> None:
        raw = {"Goals": "30", "Unknown": "999"}
        result = apply_column_map(raw, self.COLUMN_MAP)
        assert "Unknown" not in result
        assert result == {"g": 30}

    def test_empty_string_becomes_none_and_is_stripped(self) -> None:
        raw = {"Goals": "", "Assists": "40"}
        result = apply_column_map(raw, self.COLUMN_MAP)
        assert "g" not in result  # None values stripped
        assert result["a"] == 40

    def test_dash_becomes_none_and_is_stripped(self) -> None:
        raw = {"Goals": "-", "Assists": "10"}
        result = apply_column_map(raw, self.COLUMN_MAP)
        assert "g" not in result

    def test_decimal_truncated_to_int(self) -> None:
        raw = {"Goals": "29.7"}
        result = apply_column_map(raw, self.COLUMN_MAP)
        assert result["g"] == 29

    def test_empty_row_returns_empty_dict(self) -> None:
        assert apply_column_map({}, self.COLUMN_MAP) == {}


class TestUpsertSource:
    def test_calls_upsert_on_sources_table(self) -> None:
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value.data = [
            {"id": "src-1"}
        ]
        result = upsert_source(mock_db, "hashtag_hockey", "Hashtag Hockey")
        mock_db.table.assert_called_once_with("sources")
        assert result == "src-1"


class TestFetchPlayersAndAliases:
    def test_returns_players_and_aliases(self) -> None:
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.execute.return_value.data = []
        players, aliases = fetch_players_and_aliases(mock_db)
        assert players == []
        assert aliases == []
```

- [ ] **Step 4: Run helper tests**

```bash
cd apps/api && pytest tests/scrapers/projection/test_helpers.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/api/scrapers/projection/__init__.py apps/api/tests/scrapers/projection/
git commit -m "feat(scrapers): add shared projection scraper helpers and column mapper"
```

---

## Chunk 3: HashtagHockey Scraper

### Task 5: Inspect HashtagHockey site and create HTML fixture

- [ ] **Step 1: Inspect hashtag-hockey.com projections page**

Visit `https://hashtag-hockey.com` and locate the pre-season skater projection table.

Check if it's JS-rendered:
```bash
curl -s "https://hashtag-hockey.com" | grep -i "skater\|projection\|<table"
```

If `<table>` appears in the raw HTML → use `requests` + `BeautifulSoup`.
If not → use Playwright.

- [ ] **Step 2: Save an HTML fixture**

```bash
# Save the projections page HTML for tests
curl -s "<PROJECTIONS_URL>" > apps/api/tests/scrapers/fixtures/hashtag_hockey.html
```

If JS-rendered, use Playwright to save:
```python
# One-time script — run manually, save output as fixture
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    br = p.chromium.launch()
    page = br.new_page()
    page.goto("<URL>")
    page.wait_for_selector("table")
    open("hashtag_hockey.html", "w").write(page.content())
    br.close()
```

---

### Task 6: Write failing test for HashtagHockey scraper

**Files:**
- Create: `apps/api/tests/scrapers/projection/test_hashtag_hockey.py`

- [ ] **Step 1: Write the test**

```python
# apps/api/tests/scrapers/projection/test_hashtag_hockey.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scrapers.projection.hashtag_hockey import HashtagHockeyScraper

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "hashtag_hockey.html"

# ---------------------------------------------------------------------------
# Unit: _parse_html
# ---------------------------------------------------------------------------

class TestParseHtml:
    def test_returns_list_of_dicts(self) -> None:
        html = FIXTURE_PATH.read_text(encoding="utf-8")
        scraper = HashtagHockeyScraper()
        rows = scraper._parse_html(html)
        assert isinstance(rows, list)
        assert len(rows) > 0

    def test_each_row_has_player_name(self) -> None:
        html = FIXTURE_PATH.read_text(encoding="utf-8")
        rows = HashtagHockeyScraper()._parse_html(html)
        for row in rows:
            assert "player_name" in row
            assert row["player_name"]

    def test_maps_goals_column(self) -> None:
        html = FIXTURE_PATH.read_text(encoding="utf-8")
        rows = HashtagHockeyScraper()._parse_html(html)
        # At least some rows should have goals projected
        rows_with_goals = [r for r in rows if r.get("g") is not None]
        assert len(rows_with_goals) > 0


# ---------------------------------------------------------------------------
# Integration: scrape()
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db() -> MagicMock:
    db = MagicMock()
    # source upsert
    db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "src-1"}]
    # players + aliases fetch
    db.table.return_value.select.return_value.execute.return_value.data = []
    # projections upsert — no-op
    return db


class TestScrape:
    @pytest.mark.asyncio
    async def test_returns_integer_row_count(self, mock_db: MagicMock) -> None:
        html = FIXTURE_PATH.read_text(encoding="utf-8")
        scraper = HashtagHockeyScraper()
        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(scraper, "_get_with_retry", new=AsyncMock(
                return_value=MagicMock(text=html)
            )),
        ):
            count = await scraper.scrape("2025-26", mock_db)
        assert isinstance(count, int)
        assert count >= 0

    @pytest.mark.asyncio
    async def test_raises_on_robots_disallow(self, mock_db: MagicMock) -> None:
        from scrapers.base import RobotsDisallowedError
        scraper = HashtagHockeyScraper()
        with patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=False)):
            with pytest.raises(RobotsDisallowedError):
                await scraper.scrape("2025-26", mock_db)
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
cd apps/api && pytest tests/scrapers/projection/test_hashtag_hockey.py -v
```

Expected: `ModuleNotFoundError: No module named 'scrapers.projection.hashtag_hockey'`

---

### Task 7: Implement HashtagHockey scraper

**Files:**
- Create: `apps/api/scrapers/projection/hashtag_hockey.py`

- [ ] **Step 1: Write the scraper (fill in COLUMN_MAP and selectors after inspecting the fixture)**

```python
# apps/api/scrapers/projection/hashtag_hockey.py
"""
HashtagHockey pre-season projection scraper.

Site: https://hashtag-hockey.com
Projection page: <FILL IN URL after inspection>
Rendered: <static HTML / JS-rendered> (inspect and fill in)
Last verified: <DATE>

COLUMN_MAP keys are the exact column headers from the site's projection table.
Update COLUMN_MAP each season if headers change.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper, RobotsDisallowedError
from scrapers.base_projection import BaseProjectionScraper
from scrapers.matching import PlayerMatcher
from scrapers.projection import (
    apply_column_map,
    fetch_players_and_aliases,
    log_unmatched,
    update_last_successful_scrape,
    upsert_source,
    upsert_projection_row,
)

logger = logging.getLogger(__name__)

# Update this URL each season — verify it still serves projection data
PROJECTIONS_URL = "https://hashtag-hockey.com/FILL_IN_PATH"

# Map site column headers → our player_projections stat columns.
# Only include columns that exist on the site; leave out anything absent.
# Keys must match the header text exactly (case-sensitive after normalisation).
COLUMN_MAP: dict[str, str] = {
    # FILL IN after inspecting the fixture HTML
    # Examples (update to match actual headers):
    # "G": "g",
    # "A": "a",
    # "PPP": "ppp",
    # "SOG": "sog",
    # "HIT": "hits",
    # "BLK": "blocks",
    # "GP": "gp",
    # "PIM": "pim",
}

PLAYER_NAME_COLUMN = "Player"  # Update to match actual column header


class HashtagHockeyScraper(BaseScraper, BaseProjectionScraper):
    SOURCE_NAME = "hashtag_hockey"
    DISPLAY_NAME = "Hashtag Hockey"

    def _parse_html(self, html: str) -> list[dict[str, Any]]:
        """Parse the projection table from raw HTML.

        Returns a list of dicts with 'player_name' + mapped stat keys.
        """
        soup = BeautifulSoup(html, "lxml")

        # FILL IN: update selector to target the correct table on the page
        table = soup.find("table")
        if not table:
            logger.warning("HashtagHockey: no <table> found in HTML")
            return []

        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        rows: list[dict[str, Any]] = []
        for tr in table.find("tbody").find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cells) != len(headers):
                continue
            raw_row = dict(zip(headers, cells))
            player_name = raw_row.get(PLAYER_NAME_COLUMN, "").strip()
            if not player_name:
                continue
            stats = apply_column_map(raw_row, COLUMN_MAP)
            rows.append({"player_name": player_name, **stats})
        return rows

    async def scrape(self, season: str, db: Any) -> int:
        if not await self._check_robots_txt(PROJECTIONS_URL):
            raise RobotsDisallowedError(
                f"robots.txt disallows scraping {PROJECTIONS_URL}"
            )

        source_id = upsert_source(db, self.SOURCE_NAME, self.DISPLAY_NAME)
        players, aliases = fetch_players_and_aliases(db)
        matcher = PlayerMatcher(players, aliases)

        response = await self._get_with_retry(PROJECTIONS_URL)
        await asyncio.sleep(self.MIN_DELAY_SECONDS)

        projection_rows = self._parse_html(response.text)
        upserted = 0
        for row in projection_rows:
            player_name = row.pop("player_name")
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
    import asyncio as _asyncio
    from core.dependencies import get_db
    _asyncio.run(HashtagHockeyScraper().scrape("2025-26", get_db()))
```

- [ ] **Step 2: Fill in COLUMN_MAP and PROJECTIONS_URL from fixture inspection**

Open the fixture at `tests/scrapers/fixtures/hashtag_hockey.html` and identify:
- Exact column header strings for G, A, PPP, SOG, HIT, BLK, GP, PIM
- The exact column header string for the player name column
- The correct CSS selector for the table (if multiple tables on page)

Update `COLUMN_MAP`, `PLAYER_NAME_COLUMN`, and `PROJECTIONS_URL` accordingly.

- [ ] **Step 3: Run HashtagHockey tests**

```bash
cd apps/api && pytest tests/scrapers/projection/test_hashtag_hockey.py -v
```

Expected: All tests pass (fixture must exist and be parseable).

- [ ] **Step 4: Run full suite**

```bash
cd apps/api && pytest tests/ -q
```

- [ ] **Step 5: Lint**

```bash
cd apps/api && ruff check . && ruff format --check .
```

- [ ] **Step 6: Commit**

```bash
git add apps/api/scrapers/projection/hashtag_hockey.py \
        apps/api/tests/scrapers/projection/test_hashtag_hockey.py \
        apps/api/tests/scrapers/fixtures/hashtag_hockey.html
git commit -m "feat(scrapers): add HashtagHockey projection scraper"
```

---

## Chunk 4: DailyFaceoff Scraper

### Task 8: Inspect DailyFaceoff and create fixture, write test, implement scraper

DailyFaceoff publishes pre-season projections. **Verify the projection page URL exists before coding** — if no projection page is found, implement as paste/upload only (same as Dobber, Task 9).

Follow the exact same pattern as Tasks 5–7, using:

```python
# apps/api/scrapers/projection/daily_faceoff.py
SOURCE_NAME = "daily_faceoff"
DISPLAY_NAME = "DailyFaceoff"
PROJECTIONS_URL = "https://www.dailyfaceoff.com/FILL_IN"
COLUMN_MAP = {
    # FILL IN after inspection
}
```

Tests go in `tests/scrapers/projection/test_daily_faceoff.py` with fixture at `tests/scrapers/fixtures/daily_faceoff.html`.

- [ ] **Step 1: Inspect dailyfaceoff.com for a projections page**
- [ ] **Step 2: Save HTML fixture**
- [ ] **Step 3: Write failing test (mirror test_hashtag_hockey.py structure)**
- [ ] **Step 4: Implement scraper (copy HashtagHockey template, update COLUMN_MAP + URL)**
- [ ] **Step 5: Fill in COLUMN_MAP from fixture**
- [ ] **Step 6: Run tests — expect pass**
- [ ] **Step 7: Run full suite + lint**
- [ ] **Step 8: Commit**

```bash
git commit -m "feat(scrapers): add DailyFaceoff projection scraper"
```

---

## Chunk 5: Dobber Scraper (Paste/Upload Mode)

Dobber Hockey projections are paywalled. This scraper **parses a CSV/Excel file supplied by the user** — no HTTP requests.

### Task 9: Write failing test for Dobber scraper

- [ ] **Step 1: Create a minimal CSV fixture**

```python
# Create a test fixture CSV manually
import pathlib
pathlib.Path("apps/api/tests/scrapers/fixtures/dobber_sample.csv").write_text(
    "Player,G,A,PPP,SOG,HIT,BLK,GP\n"
    "Connor McDavid,52,72,28,280,32,18,82\n"
    "Leon Draisaitl,45,65,30,260,40,20,82\n"
    "Unknown Player,10,10,5,80,10,5,82\n"
)
```

- [ ] **Step 2: Write the test**

```python
# apps/api/tests/scrapers/projection/test_dobber.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scrapers.projection.dobber import DobberScraper

FIXTURE_CSV = Path(__file__).parent.parent / "fixtures" / "dobber_sample.csv"

PLAYERS = [
    {"id": "p1", "name": "Connor McDavid", "nhl_id": "8478402"},
    {"id": "p2", "name": "Leon Draisaitl", "nhl_id": "8477934"},
]
ALIASES: list = []


@pytest.fixture
def mock_db() -> MagicMock:
    db = MagicMock()
    db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "src-1"}]
    # players query
    db.table.return_value.select.return_value.execute.return_value.data = []
    return db


class TestParseCsv:
    def test_returns_rows_with_player_name(self) -> None:
        rows = DobberScraper._parse_csv(FIXTURE_CSV.read_text())
        assert len(rows) >= 2
        assert all("player_name" in r for r in rows)

    def test_maps_goals(self) -> None:
        rows = DobberScraper._parse_csv(FIXTURE_CSV.read_text())
        mcdavid = next(r for r in rows if r["player_name"] == "Connor McDavid")
        assert mcdavid.get("g") == 52


class TestIngest:
    def test_returns_matched_count(self, mock_db: MagicMock) -> None:
        # Override players fetch to return our test players
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            m = MagicMock()
            if call_count <= 2:  # players + aliases
                m.execute.return_value.data = PLAYERS if call_count == 1 else ALIASES
            else:
                m.execute.return_value.data = [{"id": "src-1"}]
            return m
        mock_db.table.return_value.select.side_effect = side_effect

        scraper = DobberScraper()
        count = scraper.ingest(FIXTURE_CSV.read_text(), "2025-26", mock_db)
        assert count == 2  # McDavid + Draisaitl matched; Unknown Player skipped

    def test_unmatched_player_logged(self, mock_db: MagicMock) -> None:
        scraper = DobberScraper()
        scraper.ingest(FIXTURE_CSV.read_text(), "2025-26", mock_db)
        # scraper_logs insert should have been called for "Unknown Player"
        insert_calls = [
            call for call in mock_db.table.call_args_list
            if call.args[0] == "scraper_logs"
        ]
        assert len(insert_calls) >= 1
```

- [ ] **Step 3: Run tests — expect ImportError**

```bash
cd apps/api && pytest tests/scrapers/projection/test_dobber.py -v
```

- [ ] **Step 4: Implement Dobber scraper**

```python
# apps/api/scrapers/projection/dobber.py
"""
Dobber Hockey projection parser (paste/upload mode).

Dobber projections are paywalled. Users with a Dobber subscription
export their CSV and upload it via the custom-source upload UI.
This scraper parses that CSV and writes rows to player_projections.

No HTTP requests are made — this scraper only processes supplied text.

CSV format expected (Dobber export):
    Player, G, A, PPP, SOG, HIT, BLK, GP, PIM
    (headers may vary by season — update COLUMN_MAP if needed)
"""
from __future__ import annotations

import csv
import io
import logging
from typing import Any

from scrapers.base_projection import BaseProjectionScraper
from scrapers.matching import PlayerMatcher
from scrapers.projection import (
    apply_column_map,
    fetch_players_and_aliases,
    log_unmatched,
    update_last_successful_scrape,
    upsert_source,
    upsert_projection_row,
)

logger = logging.getLogger(__name__)

# Update if Dobber changes their CSV export headers
COLUMN_MAP: dict[str, str] = {
    "G": "g",
    "A": "a",
    "PPP": "ppp",
    "SOG": "sog",
    "HIT": "hits",
    "BLK": "blocks",
    "GP": "gp",
    "PIM": "pim",
}

PLAYER_NAME_COLUMN = "Player"


class DobberScraper(BaseProjectionScraper):
    SOURCE_NAME = "dobber"
    DISPLAY_NAME = "Dobber Hockey"

    @staticmethod
    def _parse_csv(text: str) -> list[dict[str, Any]]:
        """Parse Dobber CSV text into a list of projection dicts."""
        reader = csv.DictReader(io.StringIO(text.strip()))
        rows = []
        for raw_row in reader:
            player_name = raw_row.get(PLAYER_NAME_COLUMN, "").strip()
            if not player_name:
                continue
            stats = apply_column_map(raw_row, COLUMN_MAP)
            rows.append({"player_name": player_name, **stats})
        return rows

    def ingest(self, csv_text: str, season: str, db: Any) -> int:
        """Parse ``csv_text`` and upsert rows to player_projections.

        Used by the custom source upload handler, not the HTTP scraper path.
        Returns number of rows upserted.
        """
        source_id = upsert_source(db, self.SOURCE_NAME, self.DISPLAY_NAME)
        players, aliases = fetch_players_and_aliases(db)
        matcher = PlayerMatcher(players, aliases)

        projection_rows = self._parse_csv(csv_text)
        upserted = 0
        for row in projection_rows:
            player_name = row.pop("player_name")
            player_id = matcher.resolve(player_name)
            if player_id is None:
                log_unmatched(db, self.SOURCE_NAME, player_name, season)
                continue
            upsert_projection_row(db, player_id, source_id, season, row)
            upserted += 1

        update_last_successful_scrape(db, source_id)
        logger.info("%s: upserted %d projection rows for %s", self.DISPLAY_NAME, upserted, season)
        return upserted

    async def scrape(self, season: str, db: Any) -> int:
        """Not implemented — Dobber is paywalled; use ingest() with user-supplied CSV."""
        raise NotImplementedError(
            "Dobber scraper does not support auto-scraping. "
            "Use ingest(csv_text, season, db) with a user-supplied CSV."
        )
```

- [ ] **Step 5: Run Dobber tests — expect all to pass**

```bash
cd apps/api && pytest tests/scrapers/projection/test_dobber.py -v
```

- [ ] **Step 6: Run full suite + lint**

```bash
cd apps/api && pytest tests/ -q && ruff check .
```

- [ ] **Step 7: Commit**

```bash
git add apps/api/scrapers/projection/dobber.py \
        apps/api/tests/scrapers/projection/test_dobber.py \
        apps/api/tests/scrapers/fixtures/dobber_sample.csv
git commit -m "feat(scrapers): add Dobber Hockey CSV parser (paste/upload mode)"
```

---

## Chunk 6: Apples & Ginos + LineupExperts Scrapers

Both follow the exact same HTML scraper pattern as HashtagHockey. Build them sequentially.

### Task 10: Apples & Ginos scraper

- [ ] **Step 1: Inspect apples-ginos.com (or equivalent) for projections page; save fixture**
- [ ] **Step 2: Write failing test** (`tests/scrapers/projection/test_apples_ginos.py`) — mirror HashtagHockey test structure
- [ ] **Step 3: Implement** (`scrapers/projection/apples_ginos.py`) — copy HashtagHockey template, update `SOURCE_NAME`, `DISPLAY_NAME`, `PROJECTIONS_URL`, `COLUMN_MAP`
- [ ] **Step 4: Run tests — expect pass**
- [ ] **Step 5: Run full suite + lint**
- [ ] **Step 6: Commit**

```bash
git commit -m "feat(scrapers): add Apples & Ginos projection scraper"
```

### Task 11: LineupExperts scraper

- [ ] **Step 1: Inspect lineupexperts.com for projections page; save fixture**
- [ ] **Step 2: Write failing test** (`tests/scrapers/projection/test_lineup_experts.py`)
- [ ] **Step 3: Implement** (`scrapers/projection/lineup_experts.py`)
- [ ] **Step 4: Run tests — expect pass**
- [ ] **Step 5: Run full suite + lint**
- [ ] **Step 6: Commit**

```bash
git commit -m "feat(scrapers): add LineupExperts projection scraper"
```

---

## Chunk 7: NST Stats Scraper

### Task 12: Natural Stat Trick stats scraper (writes to player_stats)

NST provides advanced stats (Corsi, xG, etc.) that write to `player_stats`, not `player_projections`. It subclasses `BaseScraper` directly (same as NHL.com).

- [ ] **Step 1: Inspect naturalnstatrick.com — locate the skater summary table and save fixture**

```bash
# Save NST skater report HTML (adjust URL after inspection)
curl -s "https://www.naturalstattrick.com/playerteams.php?fromseason=20252026&thruseason=20252026&stype=2&sit=all&score=all&stdoi=std&rate=n&team=ALL&pos=S&loc=B&toi=0&gpfilt=none&fd=&td=&tgfrom=0&tgthru=0&lines=single&draftteam=ALL" \
  > apps/api/tests/scrapers/fixtures/nst_skaters.html
```

- [ ] **Step 2: Write failing test**

```python
# apps/api/tests/scrapers/test_nst.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scrapers.nst import NstScraper

FIXTURE = Path(__file__).parent / "fixtures" / "nst_skaters.html"


class TestParseHtml:
    def test_returns_list(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        assert isinstance(rows, list)
        assert len(rows) > 0

    def test_each_row_has_nhl_id_or_name(self) -> None:
        rows = NstScraper._parse_html(FIXTURE.read_text())
        for row in rows:
            assert "player_name" in row or "nhl_id" in row


class TestScrape:
    @pytest.mark.asyncio
    async def test_returns_int(self) -> None:
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "p1"}]
        mock_db.table.return_value.select.return_value.execute.return_value.data = []
        html = FIXTURE.read_text()
        scraper = NstScraper()
        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(scraper, "_get_with_retry", new=AsyncMock(
                return_value=MagicMock(text=html)
            )),
        ):
            count = await scraper.scrape("2025-26", mock_db)
        assert isinstance(count, int)
```

- [ ] **Step 3: Implement NstScraper**

```python
# apps/api/scrapers/nst.py
"""
Natural Stat Trick (NST) advanced stats scraper.

Writes to player_stats (Corsi, xG, iSCF/60, SH%, PDO, WAR).
Not a projection source — uses BaseScraper, not BaseProjectionScraper.

Site: https://www.naturalstattrick.com
Stats page: playerteams.php (skater summary report)
Last verified: <DATE>
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper, RobotsDisallowedError
from scrapers.matching import PlayerMatcher

logger = logging.getLogger(__name__)

# Update URL params each season
NST_URL = (
    "https://www.naturalstattrick.com/playerteams.php"
    "?fromseason={season_id}&thruseason={season_id}"
    "&stype=2&sit=all&score=all&stdoi=std&rate=n"
    "&team=ALL&pos=S&loc=B&toi=0&gpfilt=none&fd=&td="
    "&tgfrom=0&tgthru=0&lines=single&draftteam=ALL"
)

# NST column header → player_stats column
COLUMN_MAP: dict[str, str] = {
    # FILL IN after inspecting fixture — common NST columns:
    # "CF%": "cf_pct",
    # "xGF%": "xgf_pct",
    # "SH%": "sh_pct",
    # "PDO": "pdo",
    # "TOI": "toi",
    # "iCF": "icf",
    # Update with actual column headers from the fixture
}

PLAYER_NAME_COLUMN = "Player"  # Verify against fixture


class NstScraper(BaseScraper):
    SOURCE_NAME = "nst"
    DISPLAY_NAME = "Natural Stat Trick"

    @staticmethod
    def _season_id(season: str) -> str:
        """'2025-26' → '20252026'"""
        start, end_short = season.split("-")
        century = start[:2]
        return f"{start}{century}{end_short}"

    @staticmethod
    def _parse_html(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table", id="players")  # NST uses id="players" — verify
        if not table:
            table = soup.find("table")
        if not table:
            return []
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        rows = []
        tbody = table.find("tbody")
        for tr in (tbody or table).find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cells) != len(headers):
                continue
            raw_row = dict(zip(headers, cells))
            player_name = raw_row.get(PLAYER_NAME_COLUMN, "").strip()
            if not player_name:
                continue
            rows.append({"player_name": player_name, **raw_row})
        return rows

    async def scrape(self, season: str, db: Any) -> int:
        url = NST_URL.format(season_id=self._season_id(season))
        if not await self._check_robots_txt(url):
            raise RobotsDisallowedError(f"robots.txt disallows {url}")

        players = db.table("players").select("id, name, nhl_id").execute().data
        aliases = db.table("player_aliases").select("alias_name, player_id, source").execute().data
        matcher = PlayerMatcher(players, aliases)

        response = await self._get_with_retry(url)
        await asyncio.sleep(self.MIN_DELAY_SECONDS)

        raw_rows = self._parse_html(response.text)
        upserted = 0
        for raw_row in raw_rows:
            player_name = raw_row.pop("player_name", "")
            player_id = matcher.resolve(player_name)
            if player_id is None:
                logger.info("NST: unmatched player %r", player_name)
                continue

            stats: dict[str, Any] = {}
            for raw_col, stat_col in COLUMN_MAP.items():
                val = raw_row.get(raw_col)
                if val and val.strip() not in {"", "-"}:
                    try:
                        stats[stat_col] = float(val)
                    except ValueError:
                        pass

            if not stats:
                continue

            db.table("player_stats").upsert(
                {"player_id": player_id, "season": season, **stats},
                on_conflict="player_id,season",
            ).execute()
            upserted += 1

        logger.info("NST: upserted %d player_stats rows for %s", upserted, season)
        return upserted


if __name__ == "__main__":
    import asyncio as _asyncio
    from core.dependencies import get_db
    _asyncio.run(NstScraper().scrape("2025-26", get_db()))
```

- [ ] **Step 4: Fill in `COLUMN_MAP` from the NST fixture HTML**

- [ ] **Step 5: Run NST tests — expect all to pass**

```bash
cd apps/api && pytest tests/scrapers/test_nst.py -v
```

- [ ] **Step 6: Run full suite + lint**

```bash
cd apps/api && pytest tests/ -q && ruff check .
```

- [ ] **Step 7: Commit**

```bash
git add apps/api/scrapers/nst.py apps/api/tests/scrapers/test_nst.py \
        apps/api/tests/scrapers/fixtures/nst_skaters.html
git commit -m "feat(scrapers): add Natural Stat Trick stats scraper"
```

---

## Chunk 8: GitHub Actions Cron + Notion Updates

### Task 13: GitHub Actions cron workflow for pre-season scrapers

- [ ] **Step 1: Create workflow file**

```yaml
# .github/workflows/scrape-projections.yml
name: Scrape Projection Sources

on:
  schedule:
    - cron: "0 6 * * 1"  # Weekly Monday 6am UTC (pre-season)
  workflow_dispatch:      # Manual trigger

jobs:
  scrape:
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

      - name: Scrape HashtagHockey
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          REDIS_URL: ${{ secrets.REDIS_URL }}
        run: python -m scrapers.projection.hashtag_hockey

      - name: Scrape DailyFaceoff
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          REDIS_URL: ${{ secrets.REDIS_URL }}
        run: python -m scrapers.projection.daily_faceoff

      - name: Scrape Apples & Ginos
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          REDIS_URL: ${{ secrets.REDIS_URL }}
        run: python -m scrapers.projection.apples_ginos

      - name: Scrape LineupExperts
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          REDIS_URL: ${{ secrets.REDIS_URL }}
        run: python -m scrapers.projection.lineup_experts

      - name: Scrape NST
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          REDIS_URL: ${{ secrets.REDIS_URL }}
        run: python -m scrapers.nst
```

- [ ] **Step 2: Commit workflow**

```bash
git add .github/workflows/scrape-projections.yml
git commit -m "ci: add weekly pre-season projection scraper cron workflow"
```

### Task 14: Update Notion task statuses

- [ ] Mark "Write HashtagHockey projection scraper" (32548885-3275-8181-8753-cb9481ef9e6a) → Done
- [ ] Mark "Write DailyFaceoff projection scraper" (32548885-3275-81f0-85cb-e4118d5aceff) → Done
- [ ] Mark "Write Dobber Hockey projection scraper" (32048885-3275-8170-bb75-eb390cd14c2f) → Done
- [ ] Mark "Write Apples & Ginos and LineupExperts projection scrapers" (32548885-3275-81a9-b2d8-dc5f5c3b75b2) → Done
- [ ] Update `apps/api/CLAUDE.md` scrapers section

```bash
git add apps/api/CLAUDE.md
git commit -m "docs(api): mark HTML projection scrapers as complete"
```
