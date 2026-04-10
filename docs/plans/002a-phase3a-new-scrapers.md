# Phase 3a — New Scrapers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement three new scrapers that populate `sh_pct_career_avg`, `nhl_experience`, `elc_flag`, `contract_year_flag`, `speed_bursts_22`, and `top_speed` columns in `player_stats` — the remaining Tier 1/2/3 ML feature columns added in migration `003_phase3_ml_features.sql`.

**Architecture:** Each scraper subclasses `BaseScraper` from `apps/api/scrapers/base.py` and follows the `NstScraper` pattern exactly: fetch `players` and `aliases` from DB, construct `PlayerMatcher(players=..., aliases=...)`, resolve names via `matcher.resolve(name)`, upsert via `db.table("player_stats").upsert(..., on_conflict="player_id,season")`. The Hockey Reference scraper adds a `scrape_history(start, end, db)` method for one-time backfill of 20 seasons; this is the method used in the retraining cron. The annual `scrape(season, db)` method fetches only the current season and is best used after a prior `scrape_history()` has established career baselines (see Task 1 notes).

**Tech Stack:** Python 3.11+, httpx, BeautifulSoup4/lxml, pytest, MagicMock, `PlayerMatcher` + `_fetch_players`/`_fetch_aliases` helpers (existing pattern from NstScraper).

**Evolving Hockey (GAR/xGAR columns):** Per `docs/adrs/002-phase3-ml-trends-design.md` Decisions §2, Evolving Hockey is a $5/month subscription and is ingested as a **manual one-time CSV upload** via the existing `POST /sources/upload` endpoint. No automated scraper is needed or planned. The `gar` and `xgar` columns in `player_stats` are populated this way.

---

## File Map

```
CREATE  apps/api/scrapers/hockey_reference.py
CREATE  apps/api/scrapers/elite_prospects.py
CREATE  apps/api/scrapers/nhl_edge.py                    ← Task 3 (optional Tier 3)
CREATE  apps/api/tests/scrapers/test_hockey_reference.py
CREATE  apps/api/tests/scrapers/test_elite_prospects.py
CREATE  apps/api/tests/scrapers/test_nhl_edge.py         ← Task 3 (optional Tier 3)
CREATE  apps/api/tests/scrapers/fixtures/hockey_reference_2025_sample.html
CREATE  apps/api/tests/scrapers/fixtures/elite_prospects_sample.json
CREATE  apps/api/tests/scrapers/fixtures/nhl_edge_sample.json
MODIFY  apps/api/core/config.py           ← add elite_prospects_api_key
MODIFY  apps/api/.env.example             ← add ELITE_PROSPECTS_API_KEY
MODIFY  .github/workflows/retrain-trends.yml  ← add HR scraper step (correct workflow)
MODIFY  .github/workflows/scrape-projections.yml  ← add EP + NHL EDGE scraper steps
MODIFY  apps/api/CLAUDE.md                ← update Phase 3b status table
MODIFY  docs/backend-reference.md         ← add new scrapers to scraper reference
```

---

## Reference Files (read before implementing)

- `apps/api/scrapers/base.py` — `BaseScraper` ABC: `_check_robots_txt`, `_get_with_retry`, abstract `scrape()` interface
- `apps/api/scrapers/nst.py` — **canonical pattern** for new scrapers: `_fetch_players`, `_fetch_aliases`, `PlayerMatcher(players=..., aliases=...)`, `matcher.resolve(name)`, `_upsert_player_stats`
- `apps/api/scrapers/matching.py` — `PlayerMatcher(players, aliases)` constructor, `matcher.resolve(raw_name, threshold=85) → str | None`
- `apps/api/tests/scrapers/test_nst.py` — canonical test pattern (fixture HTML, `_mock_db()`, mock `_fetch_players`/`_fetch_aliases`)
- `apps/api/tests/scrapers/fixtures/nst_skaters.html` — example minimal HTML fixture format
- `.github/workflows/scrape-projections.yml` — existing `python -m scrapers.X` invocation style

---

## Task 1: Hockey Reference Scraper

**Purpose:** Populate `sh_pct_career_avg` (Tier 1) and `nhl_experience` (Tier 2) in `player_stats`.

**URL pattern:** `https://www.hockey-reference.com/leagues/NHL_{year}_skaters.html`
where `year` = 4-digit end year: `"2024-25"` → `2025`.

**Critical:** Hockey Reference robots.txt specifies `Crawl-delay: 3`. `MIN_DELAY_SECONDS = 3.0` is mandatory.

**Career SH% logic:** `sh_pct_career_avg` = cumulative career goals / cumulative career shots through that season. Computed across multiple seasons in `_compute_career_stats()`. `nhl_experience` = count of seasons with GP > 0.

**`scrape()` vs `scrape_history()`:**
- `scrape_history(start, end, db)` — fetches ALL seasons in range, computes exact career running totals, upserts every `(player, season)` pair. Use this for the one-time backfill AND as the annual retraining step (called from `retrain-trends.yml`).
- `scrape(season, db)` — convenience wrapper: fetches only the current season, queries DB for the player's existing `sh_pct_career_avg` and `nhl_experience` from the most recent prior row, and computes the new season's values. Suitable for lightweight annual updates if history already exists in DB. Does NOT replace `scrape_history()` for the initial backfill.

**Files:**
- Create: `apps/api/scrapers/hockey_reference.py`
- Create: `apps/api/tests/scrapers/test_hockey_reference.py`
- Create: `apps/api/tests/scrapers/fixtures/hockey_reference_2025_sample.html`

---

- [ ] **Step 1.0: Apply DB migration for career_goals and career_shots**

`HockeyReferenceScraper` stores raw career totals so that incremental `scrape()` runs can accumulate correctly. These columns must exist before the scraper runs.

Create or append to a migration file (e.g. `supabase/migrations/004_hr_career_totals.sql`):

```sql
alter table player_stats add column if not exists career_goals integer;
alter table player_stats add column if not exists career_shots integer;
```

Apply via Supabase dashboard or CLI:
```bash
supabase db push   # or run the SQL directly in the Supabase SQL editor
```

Expected: migration succeeds with no errors.

---

- [ ] **Step 1.1: Create the HTML fixture**

Save to `apps/api/tests/scrapers/fixtures/hockey_reference_2025_sample.html`:

```html
<!DOCTYPE html>
<html>
<body>
<table id="stats">
  <thead>
    <tr>
      <th data-stat="player">Player</th>
      <th data-stat="team_id">Tm</th>
      <th data-stat="games_played">GP</th>
      <th data-stat="goals">G</th>
      <th data-stat="shots">S</th>
      <th data-stat="shot_pct">S%</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td data-stat="player"><a href="/players/m/mcdavid01.html">Connor McDavid</a></td>
      <td data-stat="team_id">EDM</td>
      <td data-stat="games_played">82</td>
      <td data-stat="goals">32</td>
      <td data-stat="shots">200</td>
      <td data-stat="shot_pct">16.0</td>
    </tr>
    <tr>
      <td data-stat="player"><a href="/players/m/mackinn01.html">Nathan MacKinnon</a></td>
      <td data-stat="team_id">COL</td>
      <td data-stat="games_played">80</td>
      <td data-stat="goals">28</td>
      <td data-stat="shots">250</td>
      <td data-stat="shot_pct">11.2</td>
    </tr>
    <!-- mid-table header row — must be skipped -->
    <tr class="thead">
      <td data-stat="player"></td>
      <td data-stat="team_id"></td>
      <td data-stat="games_played"></td>
      <td data-stat="goals"></td>
      <td data-stat="shots"></td>
      <td data-stat="shot_pct"></td>
    </tr>
    <tr>
      <td data-stat="player"><a href="/players/d/draisai01.html">Leon Draisaitl</a></td>
      <td data-stat="team_id">EDM</td>
      <td data-stat="games_played">75</td>
      <td data-stat="goals">41</td>
      <td data-stat="shots">220</td>
      <td data-stat="shot_pct">18.6</td>
    </tr>
  </tbody>
</table>
</body>
</html>
```

---

- [ ] **Step 1.2: Write failing tests**

Create `apps/api/tests/scrapers/test_hockey_reference.py`:

```python
"""TDD tests for scrapers/hockey_reference.py. All HTTP and DB I/O is mocked."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from scrapers.hockey_reference import HockeyReferenceScraper

FIXTURE = Path(__file__).parent / "fixtures" / "hockey_reference_2025_sample.html"
SEASON = "2024-25"

_PLAYERS = [
    {"id": "p-mcdavid", "name": "Connor McDavid"},
    {"id": "p-mackinnon", "name": "Nathan MacKinnon"},
    {"id": "p-draisaitl", "name": "Leon Draisaitl"},
]
_ALIASES: list[dict] = []


def _make_response(text: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=text, request=httpx.Request("GET", "http://x"))


def _mock_db(prior_data: list[dict] | None = None) -> MagicMock:
    """Build a minimal DB mock for HockeyReferenceScraper tests.

    All TestScrape tests patch _fetch_players and _fetch_aliases directly via
    patch.object, so this mock only needs to cover:
      - _fetch_prior_career: .select(...).lt(...).execute().data
      - upsert: .upsert(...).execute().data
    """
    db = MagicMock()
    # _fetch_prior_career path: db.table("player_stats").select(...).lt(...).execute().data
    if prior_data is not None:
        db.table.return_value.select.return_value.lt.return_value.execute.return_value.data = prior_data
    # upsert
    db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "p-1"}]
    return db


# ---------------------------------------------------------------------------
# Season year conversion
# ---------------------------------------------------------------------------

class TestSeasonToYear:
    def test_2024_25(self) -> None:
        assert HockeyReferenceScraper._season_to_year("2024-25") == 2025

    def test_2005_06(self) -> None:
        assert HockeyReferenceScraper._season_to_year("2005-06") == 2006

    def test_2099_00(self) -> None:
        assert HockeyReferenceScraper._season_to_year("2099-00") == 2100


# ---------------------------------------------------------------------------
# URL building
# ---------------------------------------------------------------------------

class TestBuildUrl:
    def test_uses_end_year(self) -> None:
        assert "NHL_2025_skaters" in HockeyReferenceScraper._build_url("2024-25")

    def test_domain(self) -> None:
        assert "hockey-reference.com" in HockeyReferenceScraper._build_url("2024-25")


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------

class TestParseHtml:
    def test_returns_three_players(self) -> None:
        rows = HockeyReferenceScraper._parse_html(FIXTURE.read_text())
        assert len(rows) == 3

    def test_each_row_has_player_name(self) -> None:
        for row in HockeyReferenceScraper._parse_html(FIXTURE.read_text()):
            assert row["player_name"]

    def test_parses_goals_and_shots(self) -> None:
        rows = HockeyReferenceScraper._parse_html(FIXTURE.read_text())
        mcdavid = next(r for r in rows if "McDavid" in r["player_name"])
        assert mcdavid["goals"] == 32
        assert mcdavid["shots"] == 200

    def test_parses_gp(self) -> None:
        rows = HockeyReferenceScraper._parse_html(FIXTURE.read_text())
        assert next(r for r in rows if "McDavid" in r["player_name"])["gp"] == 82

    def test_skips_thead_class_rows(self) -> None:
        rows = HockeyReferenceScraper._parse_html(FIXTURE.read_text())
        assert all(r["player_name"] for r in rows)

    def test_zero_shots_gives_none_sh_pct(self) -> None:
        html = FIXTURE.read_text().replace(
            '<td data-stat="shots">200</td>', '<td data-stat="shots">0</td>'
        )
        rows = HockeyReferenceScraper._parse_html(html)
        mcdavid = next(r for r in rows if "McDavid" in r["player_name"])
        assert mcdavid["sh_pct"] is None

    def test_missing_table_returns_empty(self) -> None:
        assert HockeyReferenceScraper._parse_html("<html><body></body></html>") == []


# ---------------------------------------------------------------------------
# Career stats accumulation (_compute_career_stats)
# ---------------------------------------------------------------------------

class TestComputeCareerStats:
    def test_single_season(self) -> None:
        rows = {"2024-25": [{"player_name": "P", "goals": 20, "shots": 100, "gp": 82}]}
        result = HockeyReferenceScraper._compute_career_stats(rows)
        assert result["P"]["2024-25"]["sh_pct_career_avg"] == pytest.approx(0.20)
        assert result["P"]["2024-25"]["nhl_experience"] == 1

    def test_two_seasons_accumulates(self) -> None:
        rows = {
            "2023-24": [{"player_name": "P", "goals": 10, "shots": 100, "gp": 70}],
            "2024-25": [{"player_name": "P", "goals": 20, "shots": 100, "gp": 82}],
        }
        result = HockeyReferenceScraper._compute_career_stats(rows)
        # career through 2024-25: 30G / 200S = 0.15
        assert result["P"]["2024-25"]["sh_pct_career_avg"] == pytest.approx(0.15)
        assert result["P"]["2024-25"]["nhl_experience"] == 2

    def test_zero_shot_season_excluded_from_denominator(self) -> None:
        rows = {
            "2023-24": [{"player_name": "P", "goals": 0, "shots": 0, "gp": 5}],
            "2024-25": [{"player_name": "P", "goals": 10, "shots": 100, "gp": 70}],
        }
        result = HockeyReferenceScraper._compute_career_stats(rows)
        assert result["P"]["2024-25"]["sh_pct_career_avg"] == pytest.approx(0.10)
        assert result["P"]["2024-25"]["nhl_experience"] == 2

    def test_out_of_order_seasons_processed_chronologically(self) -> None:
        rows = {
            "2024-25": [{"player_name": "P", "goals": 20, "shots": 100, "gp": 82}],
            "2023-24": [{"player_name": "P", "goals": 10, "shots": 100, "gp": 70}],
        }
        result = HockeyReferenceScraper._compute_career_stats(rows)
        assert result["P"]["2023-24"]["nhl_experience"] == 1
        assert result["P"]["2024-25"]["nhl_experience"] == 2


# ---------------------------------------------------------------------------
# scrape() — single-season path, uses DB for prior career context
# ---------------------------------------------------------------------------

class TestScrape:
    @pytest.mark.asyncio
    async def test_returns_upserted_count(self) -> None:
        scraper = HockeyReferenceScraper()
        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(scraper, "_get_with_retry", new=AsyncMock(return_value=_make_response(FIXTURE.read_text()))),
            patch.object(scraper, "_fetch_players", return_value=_PLAYERS),
            patch.object(scraper, "_fetch_aliases", return_value=_ALIASES),
        ):
            count = await scraper.scrape(SEASON, _mock_db())
        assert count == 3

    @pytest.mark.asyncio
    async def test_robots_disallowed_raises(self) -> None:
        from scrapers.base import RobotsDisallowedError
        scraper = HockeyReferenceScraper()
        with patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=False)):
            with pytest.raises(RobotsDisallowedError):
                await scraper.scrape(SEASON, MagicMock())

    @pytest.mark.asyncio
    async def test_upserts_sh_pct_career_avg(self) -> None:
        scraper = HockeyReferenceScraper()
        upserted: list[dict] = []

        def capture(payload, on_conflict=None):
            upserted.append(payload)
            m = MagicMock()
            m.execute.return_value.data = [{"id": "p-1"}]
            return m

        db = _mock_db()
        db.table.return_value.upsert.side_effect = capture

        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(scraper, "_get_with_retry", new=AsyncMock(return_value=_make_response(FIXTURE.read_text()))),
            patch.object(scraper, "_fetch_players", return_value=_PLAYERS),
            patch.object(scraper, "_fetch_aliases", return_value=_ALIASES),
        ):
            await scraper.scrape(SEASON, db)

        assert any("sh_pct_career_avg" in p for p in upserted)
        assert any("nhl_experience" in p for p in upserted)

    @pytest.mark.asyncio
    async def test_incorporates_prior_db_career_stats(self) -> None:
        """scrape() must add current season to prior career totals from DB."""
        scraper = HockeyReferenceScraper()
        # Prior DB data: McDavid had 10G / 100S career through 2023-24, 1 season
        prior_data = [
            {
                "player_id": "p-mcdavid",
                "season": "2023-24",
                "career_goals": 10,
                "career_shots": 100,
                "nhl_experience": 1,
            }
        ]
        upserted: list[dict] = []

        def capture(payload, on_conflict=None):
            upserted.append(payload)
            m = MagicMock()
            m.execute.return_value.data = [{"id": "p-1"}]
            return m

        db = _mock_db(prior_data=prior_data)
        db.table.return_value.upsert.side_effect = capture

        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(scraper, "_get_with_retry", new=AsyncMock(return_value=_make_response(FIXTURE.read_text()))),
            patch.object(scraper, "_fetch_players", return_value=_PLAYERS),
            patch.object(scraper, "_fetch_aliases", return_value=_ALIASES),
        ):
            await scraper.scrape(SEASON, db)

        # McDavid in fixture has 32G / 200S in 2024-25
        # Combined: 42G / 300S = 0.14, experience = 2
        mcdavid_upsert = next(p for p in upserted if p.get("player_id") == "p-mcdavid")
        assert mcdavid_upsert["sh_pct_career_avg"] == pytest.approx(42 / 300, abs=0.001)
        assert mcdavid_upsert["nhl_experience"] == 2

    @pytest.mark.asyncio
    async def test_unmatched_player_skipped(self) -> None:
        scraper = HockeyReferenceScraper()
        db = _mock_db()
        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(scraper, "_get_with_retry", new=AsyncMock(return_value=_make_response(FIXTURE.read_text()))),
            patch.object(scraper, "_fetch_players", return_value=[]),   # no players → no matches
            patch.object(scraper, "_fetch_aliases", return_value=[]),
        ):
            count = await scraper.scrape(SEASON, db)
        db.table.return_value.upsert.assert_not_called()
        assert count == 0
```

Run: `cd apps/api && pytest tests/scrapers/test_hockey_reference.py -v`
Expected: **ImportError / ModuleNotFoundError** (file doesn't exist yet).

---

- [ ] **Step 1.3: Implement `HockeyReferenceScraper`**

Create `apps/api/scrapers/hockey_reference.py`:

```python
"""
Hockey Reference stats scraper.

Fetches per-season goals and shots for all skaters. Computes rolling career
SH% and NHL experience, then upserts them into ``player_stats``.

Target URL (example — 2024-25 season):
  https://www.hockey-reference.com/leagues/NHL_2025_skaters.html

robots.txt specifies Crawl-delay: 3 — MIN_DELAY_SECONDS enforces this.

Two modes:
  scrape_history(start, end, db)  — full backfill; use for initial load and
                                    the annual retraining cron.
  scrape(season, db)              — incremental; fetches current season from
                                    HR, loads prior career totals from DB,
                                    upserts the new season's values.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper, RobotsDisallowedError
from scrapers.matching import PlayerMatcher

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.hockey-reference.com/leagues/NHL_{year}_skaters.html"


class HockeyReferenceScraper(BaseScraper):
    """Scrapes Hockey Reference for career SH% and NHL experience."""

    MIN_DELAY_SECONDS = 3.0  # robots.txt Crawl-delay

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _season_to_year(season: str) -> int:
        """'2024-25' → 2025  |  '2099-00' → 2100"""
        year1 = int(season.split("-")[0])
        return year1 + 1

    @staticmethod
    def _build_url(season: str) -> str:
        return _BASE_URL.format(year=HockeyReferenceScraper._season_to_year(season))

    @staticmethod
    def _parse_html(html: str) -> list[dict[str, Any]]:
        """Parse the ``id="stats"`` skaters table.

        Returns list of dicts: player_name, gp, goals, shots, sh_pct (None if shots==0).
        Skips rows with class "thead" (mid-table repeat headers).
        """
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table", {"id": "stats"})
        if table is None:
            logger.warning("Hockey Reference: table id='stats' not found")
            return []

        rows: list[dict[str, Any]] = []
        for tr in table.find("tbody").find_all("tr"):
            if "thead" in (tr.get("class") or []):
                continue
            td = tr.find("td", {"data-stat": "player"})
            if td is None:
                continue
            player_name = td.get_text(strip=True)
            if not player_name:
                continue

            def _int(stat: str) -> int:
                cell = tr.find("td", {"data-stat": stat})
                txt = cell.get_text(strip=True) if cell else ""
                return int(txt) if txt else 0

            goals = _int("goals")
            shots = _int("shots")
            rows.append({
                "player_name": player_name,
                "gp": _int("games_played"),
                "goals": goals,
                "shots": shots,
                "sh_pct": (goals / shots) if shots > 0 else None,
            })

        return rows

    @staticmethod
    def _compute_career_stats(
        rows_by_season: dict[str, list[dict[str, Any]]],
    ) -> dict[str, dict[str, dict[str, Any]]]:
        """Accumulate per-player career running totals across seasons.

        Returns: {player_name: {season: {sh_pct_career_avg, career_goals,
                                          career_shots, nhl_experience}}}
        Seasons processed in chronological order regardless of dict insertion order.
        """
        running: dict[str, dict[str, Any]] = {}
        result: dict[str, dict[str, dict[str, Any]]] = {}

        for season in sorted(rows_by_season):
            for row in rows_by_season[season]:
                name = row["player_name"]
                acc = running.setdefault(name, {"goals": 0, "shots": 0, "experience": 0})

                acc["goals"] += row.get("goals", 0)
                acc["shots"] += row.get("shots", 0)
                if row.get("gp", 0) > 0:
                    acc["experience"] += 1

                sh_pct_career = acc["goals"] / acc["shots"] if acc["shots"] > 0 else None
                result.setdefault(name, {})[season] = {
                    "sh_pct_career_avg": sh_pct_career,
                    "career_goals": acc["goals"],
                    "career_shots": acc["shots"],
                    "nhl_experience": acc["experience"],
                }

        return result

    # ------------------------------------------------------------------
    # DB helpers (follow NstScraper pattern exactly)
    # ------------------------------------------------------------------

    def _fetch_players(self, db: Any) -> list[dict[str, Any]]:
        return db.table("players").select("id,name").execute().data or []

    def _fetch_aliases(self, db: Any) -> list[dict[str, Any]]:
        return db.table("player_aliases").select("alias_name,player_id,source").execute().data or []

    def _fetch_prior_career(
        self, db: Any, season: str
    ) -> dict[str, dict[str, Any]]:
        """Return most-recent-prior-season career totals keyed by player_id."""
        rows = (
            db.table("player_stats")
            .select("player_id,season,career_goals,career_shots,nhl_experience")
            .lt("season", season)
            .execute()
            .data
            or []
        )
        # Keep only the most recent season per player
        best: dict[str, dict[str, Any]] = {}
        for row in rows:
            pid = row["player_id"]
            if pid not in best or row["season"] > best[pid]["season"]:
                best[pid] = row
        return best

    def _upsert_player_stats(
        self,
        db: Any,
        player_id: str,
        season: str,
        sh_pct_career_avg: float | None,
        career_goals: int,
        career_shots: int,
        nhl_experience: int,
    ) -> None:
        payload: dict[str, Any] = {
            "player_id": player_id,
            "season": season,
            "career_goals": career_goals,
            "career_shots": career_shots,
            "nhl_experience": nhl_experience,
        }
        if sh_pct_career_avg is not None:
            payload["sh_pct_career_avg"] = round(sh_pct_career_avg, 4)
        db.table("player_stats").upsert(payload, on_conflict="player_id,season").execute()

    # ------------------------------------------------------------------
    # Scrape interface
    # ------------------------------------------------------------------

    async def scrape(self, season: str, db: Any) -> int:
        """Fetch one season from HR, merge with prior DB career totals, upsert.

        Best used when ``scrape_history()`` has already established career
        baselines in the DB. Without prior data, treats this as the player's
        first season (career totals = current season only).
        """
        url = self._build_url(season)
        if not await self._check_robots_txt(url):
            raise RobotsDisallowedError(f"robots.txt disallows {url}")

        response = await self._get_with_retry(url)
        rows = self._parse_html(response.text)

        players = self._fetch_players(db)
        aliases = self._fetch_aliases(db)
        matcher = PlayerMatcher(players=players, aliases=aliases)
        prior = self._fetch_prior_career(db, season)

        count = 0
        for row in rows:
            player_id = matcher.resolve(row["player_name"])
            if player_id is None:
                logger.debug("Hockey Reference: unmatched %r — skipping", row["player_name"])
                continue

            prev = prior.get(player_id, {})
            career_goals = prev.get("career_goals", 0) + row["goals"]
            career_shots = prev.get("career_shots", 0) + row["shots"]
            experience = prev.get("nhl_experience", 0) + (1 if row["gp"] > 0 else 0)
            sh_pct_career = career_goals / career_shots if career_shots > 0 else None

            self._upsert_player_stats(
                db, player_id, season, sh_pct_career, career_goals, career_shots, experience
            )
            count += 1

        logger.info("Hockey Reference: upserted %d rows for %s", count, season)
        return count

    async def scrape_history(
        self, start_season: str, end_season: str, db: Any
    ) -> int:
        """Full backfill: fetch all seasons in [start, end], compute exact career totals.

        Fetches each season page sequentially respecting the 3s crawl delay.
        Returns total rows upserted.
        """
        if not await self._check_robots_txt(self._build_url(start_season)):
            raise RobotsDisallowedError("robots.txt disallows Hockey Reference scraping")

        start_year = self._season_to_year(start_season) - 1
        end_year = self._season_to_year(end_season) - 1
        seasons = [f"{y}-{str(y + 1)[2:]}" for y in range(start_year, end_year + 1)]

        rows_by_season: dict[str, list[dict[str, Any]]] = {}
        for i, season in enumerate(seasons):
            response = await self._get_with_retry(self._build_url(season))
            rows_by_season[season] = self._parse_html(response.text)
            logger.info("Hockey Reference: fetched %s (%d/%d)", season, i + 1, len(seasons))
            if i < len(seasons) - 1:
                await asyncio.sleep(self.MIN_DELAY_SECONDS)

        career_result = self._compute_career_stats(rows_by_season)
        players = self._fetch_players(db)
        aliases = self._fetch_aliases(db)
        matcher = PlayerMatcher(players=players, aliases=aliases)

        total = 0
        for player_name, season_data in career_result.items():
            player_id = matcher.resolve(player_name)
            if player_id is None:
                continue
            for season, stats in season_data.items():
                self._upsert_player_stats(
                    db,
                    player_id,
                    season,
                    stats.get("sh_pct_career_avg"),
                    stats["career_goals"],
                    stats["career_shots"],
                    stats["nhl_experience"],
                )
                total += 1

        logger.info("Hockey Reference history: %d rows upserted", total)
        return total
```

> **Note:** This implementation stores `career_goals` and `career_shots` alongside `sh_pct_career_avg` in `player_stats` to enable correct incremental updates in `scrape()`. These columns need to be added to the DB schema. Add them to `supabase/migrations/003_phase3_ml_features.sql` (or a new migration `004_hr_career_totals.sql`):
>
> ```sql
> alter table player_stats add column if not exists career_goals integer;
> alter table player_stats add column if not exists career_shots integer;
> ```

- [ ] **Step 1.4: Run tests — all should pass**

```bash
cd apps/api && pytest tests/scrapers/test_hockey_reference.py -v
```
Expected: all green. If `test_incorporates_prior_db_career_stats` fails, debug the `_fetch_prior_career` DB mock chain — ensure `db.table("player_stats").select(...).lt(...).execute().data` is correctly set up in `_mock_db(prior_data=...)`.

- [ ] **Step 1.5: Run full suite to confirm no regressions**

```bash
cd apps/api && pytest --tb=short -q
```
Expected: 571 + new HR tests, all green.

- [ ] **Step 1.6: Commit**

```bash
git add apps/api/scrapers/hockey_reference.py \
        apps/api/tests/scrapers/test_hockey_reference.py \
        apps/api/tests/scrapers/fixtures/hockey_reference_2025_sample.html
git commit -m "feat(phase3a): add Hockey Reference scraper (sh_pct_career_avg, nhl_experience)"
```

---

## Task 2: Elite Prospects Scraper

**Purpose:** Populate `elc_flag` and `contract_year_flag` (Tier 3) in `player_stats`.

**API:** `https://api.eliteprospects.com/v1/` — free tier, requires `ELITE_PROSPECTS_API_KEY`.
- Endpoint: `GET /player-stats?league.slug=nhl&season.slug={slug}&limit=100&offset={n}&apiKey={key}`
- Season slug format: `"2024-25"` → `"2024-2025"`
- ELC flag: `player.contract.type == "ELC"`
- Contract year: `player.contract.expiryYear == season_end_year`

> **Important:** The fixture uses approximate field names. Before finalizing, make one real API call and inspect the actual response. Update `_parse_response` and the fixture to match. The test structure will remain the same regardless.

**Files:**
- Create: `apps/api/scrapers/elite_prospects.py`
- Create: `apps/api/tests/scrapers/test_elite_prospects.py`
- Create: `apps/api/tests/scrapers/fixtures/elite_prospects_sample.json`
- Modify: `apps/api/core/config.py` — add `elite_prospects_api_key: str = ""`
- Modify: `apps/api/.env.example` — add `ELITE_PROSPECTS_API_KEY=`

---

- [ ] **Step 2.1: Add config setting**

In `apps/api/core/config.py`, add to the `Settings` class:
```python
elite_prospects_api_key: str = ""
```

In `apps/api/.env.example`:
```
ELITE_PROSPECTS_API_KEY=         # free tier — get at eliteprospects.com/api
```

- [ ] **Step 2.2: Create the JSON fixture**

Save to `apps/api/tests/scrapers/fixtures/elite_prospects_sample.json`:

```json
{
  "data": [
    {
      "player": {
        "firstName": "Connor",
        "lastName": "McDavid",
        "contract": { "type": "SPC", "expiryYear": 2026 }
      }
    },
    {
      "player": {
        "firstName": "Matvei",
        "lastName": "Michkov",
        "contract": { "type": "ELC", "expiryYear": 2025 }
      }
    },
    {
      "player": {
        "firstName": "Nico",
        "lastName": "Hischier",
        "contract": { "type": "SPC", "expiryYear": 2025 }
      }
    }
  ],
  "total": 3,
  "limit": 100,
  "offset": 0
}
```

*Season 2024-25 → end year 2025. McDavid: no flags. Michkov: ELC=True, contract_year=True. Hischier: ELC=False, contract_year=True.*

- [ ] **Step 2.3: Write failing tests**

Create `apps/api/tests/scrapers/test_elite_prospects.py`:

```python
"""TDD tests for scrapers/elite_prospects.py. All HTTP and DB I/O is mocked."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from scrapers.elite_prospects import EliteProspectsScraper

FIXTURE = Path(__file__).parent / "fixtures" / "elite_prospects_sample.json"
SEASON = "2024-25"

_PLAYERS = [
    {"id": "p-mcdavid", "name": "Connor McDavid"},
    {"id": "p-michkov", "name": "Matvei Michkov"},
    {"id": "p-hischier", "name": "Nico Hischier"},
]
_ALIASES: list[dict] = []


def _make_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=json.dumps(data), request=httpx.Request("GET", "http://x"))


def _mock_db() -> MagicMock:
    """Minimal DB mock — all TestScrape tests patch _fetch_players/_fetch_aliases directly."""
    db = MagicMock()
    db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "p-1"}]
    return db


# ---------------------------------------------------------------------------
# Season helpers
# ---------------------------------------------------------------------------

class TestSeasonHelpers:
    def test_season_slug_2024_25(self) -> None:
        assert EliteProspectsScraper._season_slug("2024-25") == "2024-2025"

    def test_season_slug_2005_06(self) -> None:
        assert EliteProspectsScraper._season_slug("2005-06") == "2005-2006"

    def test_season_end_year(self) -> None:
        assert EliteProspectsScraper._season_end_year("2024-25") == 2025


# ---------------------------------------------------------------------------
# _parse_response
# ---------------------------------------------------------------------------

class TestParseResponse:
    def setup_method(self) -> None:
        self.data = json.loads(FIXTURE.read_text())["data"]

    def test_returns_three_rows(self) -> None:
        assert len(EliteProspectsScraper._parse_response(self.data, 2025)) == 3

    def test_elc_flag_true_for_elc(self) -> None:
        rows = EliteProspectsScraper._parse_response(self.data, 2025)
        michkov = next(r for r in rows if "Michkov" in r["player_name"])
        assert michkov["elc_flag"] is True

    def test_elc_flag_false_for_spc(self) -> None:
        rows = EliteProspectsScraper._parse_response(self.data, 2025)
        assert not next(r for r in rows if "McDavid" in r["player_name"])["elc_flag"]

    def test_contract_year_true_when_expiry_matches(self) -> None:
        rows = EliteProspectsScraper._parse_response(self.data, 2025)
        assert next(r for r in rows if "Hischier" in r["player_name"])["contract_year_flag"]

    def test_contract_year_false_when_expiry_after_season(self) -> None:
        rows = EliteProspectsScraper._parse_response(self.data, 2025)
        assert not next(r for r in rows if "McDavid" in r["player_name"])["contract_year_flag"]

    def test_missing_contract_defaults_to_false(self) -> None:
        rows = EliteProspectsScraper._parse_response(
            [{"player": {"firstName": "Test", "lastName": "Player"}}], 2025
        )
        assert rows[0]["elc_flag"] is False
        assert rows[0]["contract_year_flag"] is False


# ---------------------------------------------------------------------------
# scrape()
# ---------------------------------------------------------------------------

class TestScrape:
    @pytest.mark.asyncio
    async def test_returns_upserted_count(self) -> None:
        scraper = EliteProspectsScraper(api_key="test-key")
        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(scraper, "_get_with_retry", new=AsyncMock(return_value=_make_response(json.loads(FIXTURE.read_text())))),
            patch.object(scraper, "_fetch_players", return_value=_PLAYERS),
            patch.object(scraper, "_fetch_aliases", return_value=_ALIASES),
        ):
            assert await scraper.scrape(SEASON, _mock_db()) == 3

    @pytest.mark.asyncio
    async def test_missing_api_key_raises(self) -> None:
        scraper = EliteProspectsScraper(api_key="")
        with pytest.raises(ValueError, match="ELITE_PROSPECTS_API_KEY"):
            await scraper.scrape(SEASON, _mock_db())

    @pytest.mark.asyncio
    async def test_robots_disallowed_raises(self) -> None:
        from scrapers.base import RobotsDisallowedError
        scraper = EliteProspectsScraper(api_key="key")
        with patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=False)):
            with pytest.raises(RobotsDisallowedError):
                await scraper.scrape(SEASON, _mock_db())

    @pytest.mark.asyncio
    async def test_unmatched_player_skipped(self) -> None:
        scraper = EliteProspectsScraper(api_key="key")
        db = _mock_db()
        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(scraper, "_get_with_retry", new=AsyncMock(return_value=_make_response(json.loads(FIXTURE.read_text())))),
            patch.object(scraper, "_fetch_players", return_value=[]),
            patch.object(scraper, "_fetch_aliases", return_value=[]),
        ):
            count = await scraper.scrape(SEASON, db)
        db.table.return_value.upsert.assert_not_called()
        assert count == 0

    @pytest.mark.asyncio
    async def test_paginates(self) -> None:
        scraper = EliteProspectsScraper(api_key="key")
        p1 = {"data": [{"player": {"firstName": "A", "lastName": "B"}}], "total": 2, "limit": 1, "offset": 0}
        p2 = {"data": [{"player": {"firstName": "C", "lastName": "D"}}], "total": 2, "limit": 1, "offset": 1}
        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(scraper, "_get_with_retry", new=AsyncMock(side_effect=[_make_response(p1), _make_response(p2)])),
            patch.object(scraper, "_fetch_players", return_value=[
                {"id": "p1", "name": "A B"}, {"id": "p2", "name": "C D"}
            ]),
            patch.object(scraper, "_fetch_aliases", return_value=[]),
        ):
            assert await scraper.scrape(SEASON, _mock_db()) == 2
```

Run: `cd apps/api && pytest tests/scrapers/test_elite_prospects.py -v`
Expected: **ImportError** (file doesn't exist yet).

- [ ] **Step 2.4: Implement `EliteProspectsScraper`**

Create `apps/api/scrapers/elite_prospects.py`:

```python
"""
Elite Prospects scraper.

Fetches contract type and expiry year for NHL skaters and upserts
``elc_flag`` and ``contract_year_flag`` into ``player_stats``.

Requires ELITE_PROSPECTS_API_KEY (free tier from eliteprospects.com/api).
Rate limit on free tier: ~1 req/s; MIN_DELAY_SECONDS enforces this.

IMPORTANT: The fixture + _parse_response use *approximate* field names.
Make one real API call before finalising and update _parse_response +
elite_prospects_sample.json to match the actual response shape.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from scrapers.base import BaseScraper, RobotsDisallowedError
from scrapers.matching import PlayerMatcher

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.eliteprospects.com/v1"
_PAGE_SIZE = 100


class EliteProspectsScraper(BaseScraper):
    """Scrapes Elite Prospects for ELC and contract-year flags."""

    MIN_DELAY_SECONDS = 1.0

    def __init__(self, api_key: str, http=None) -> None:
        super().__init__(http)
        self._api_key = api_key

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _season_slug(season: str) -> str:
        """'2024-25' → '2024-2025'"""
        year1 = int(season.split("-")[0])
        return f"{year1}-{year1 + 1}"

    @staticmethod
    def _season_end_year(season: str) -> int:
        return int(season.split("-")[0]) + 1

    @staticmethod
    def _parse_response(
        data: list[dict[str, Any]], season_end_year: int
    ) -> list[dict[str, Any]]:
        rows = []
        for item in data:
            player = item.get("player", {})
            first = player.get("firstName", "")
            last = player.get("lastName", "")
            player_name = f"{first} {last}".strip()
            if not player_name:
                continue
            contract = player.get("contract") or {}
            expiry = contract.get("expiryYear")
            rows.append({
                "player_name": player_name,
                "elc_flag": contract.get("type") == "ELC",
                "contract_year_flag": expiry is not None and int(expiry) == season_end_year,
            })
        return rows

    # ------------------------------------------------------------------
    # DB helpers (NstScraper pattern)
    # ------------------------------------------------------------------

    def _fetch_players(self, db: Any) -> list[dict[str, Any]]:
        return db.table("players").select("id,name").execute().data or []

    def _fetch_aliases(self, db: Any) -> list[dict[str, Any]]:
        return db.table("player_aliases").select("alias_name,player_id,source").execute().data or []

    def _upsert_player_stats(
        self, db: Any, player_id: str, season: str, elc_flag: bool, contract_year_flag: bool
    ) -> None:
        db.table("player_stats").upsert(
            {
                "player_id": player_id,
                "season": season,
                "elc_flag": elc_flag,
                "contract_year_flag": contract_year_flag,
            },
            on_conflict="player_id,season",
        ).execute()

    # ------------------------------------------------------------------
    # Scrape interface
    # ------------------------------------------------------------------

    async def scrape(self, season: str, db: Any) -> int:
        if not self._api_key:
            raise ValueError("ELITE_PROSPECTS_API_KEY is not set")

        slug = self._season_slug(season)
        end_year = self._season_end_year(season)
        sample_url = f"{_BASE_URL}/player-stats?league.slug=nhl&season.slug={slug}&limit=1&offset=0&apiKey={self._api_key}"

        if not await self._check_robots_txt(sample_url):
            raise RobotsDisallowedError("robots.txt disallows Elite Prospects scraping")

        players = self._fetch_players(db)
        aliases = self._fetch_aliases(db)
        matcher = PlayerMatcher(players=players, aliases=aliases)

        offset = 0
        total = None
        count = 0

        while True:
            url = (
                f"{_BASE_URL}/player-stats"
                f"?league.slug=nhl"
                f"&season.slug={slug}"
                f"&limit={_PAGE_SIZE}"
                f"&offset={offset}"
                f"&apiKey={self._api_key}"
            )
            response = await self._get_with_retry(url)
            payload = response.json()

            if total is None:
                total = payload.get("total", 0)

            rows = self._parse_response(payload.get("data", []), end_year)
            for row in rows:
                player_id = matcher.resolve(row["player_name"])
                if player_id is None:
                    logger.debug("Elite Prospects: unmatched %r", row["player_name"])
                    continue
                self._upsert_player_stats(
                    db, player_id, season, row["elc_flag"], row["contract_year_flag"]
                )
                count += 1

            offset += len(rows)
            if not rows or offset >= total:
                break
            await asyncio.sleep(self.MIN_DELAY_SECONDS)

        logger.info("Elite Prospects: upserted %d rows for %s", count, season)
        return count
```

- [ ] **Step 2.5: Run tests — all should pass**

```bash
cd apps/api && pytest tests/scrapers/test_elite_prospects.py -v
```

- [ ] **Step 2.6: Run full suite**

```bash
cd apps/api && pytest --tb=short -q
```

- [ ] **Step 2.7: Commit**

```bash
git add apps/api/scrapers/elite_prospects.py \
        apps/api/tests/scrapers/test_elite_prospects.py \
        apps/api/tests/scrapers/fixtures/elite_prospects_sample.json \
        apps/api/core/config.py \
        apps/api/.env.example
git commit -m "feat(phase3a): add Elite Prospects scraper (elc_flag, contract_year_flag)"
```

---

## Task 3: NHL EDGE Scraper (Optional — Tier 3)

**Purpose:** Populate `speed_bursts_22` and `top_speed` in `player_stats`. Tier 3 — skip if time-constrained.

**API:** NHL Stats API, free, no key required.
- `https://api.nhle.com/stats/rest/en/skater/skating?isAggregate=true&isGame=false&start={start}&limit=100&cayenneExp=seasonId%3D{season_id}`
- `season_id` format: `"2024-25"` → `"20242025"`

> **Important:** Verify `sprintBurstsPerGame` and `topSpeed` field names against the live API before finalising. The fixture is approximate.

**Files:**
- Create: `apps/api/scrapers/nhl_edge.py`
- Create: `apps/api/tests/scrapers/test_nhl_edge.py`
- Create: `apps/api/tests/scrapers/fixtures/nhl_edge_sample.json`

---

- [ ] **Step 3.1: Create JSON fixture**

Save to `apps/api/tests/scrapers/fixtures/nhl_edge_sample.json`:

```json
{
  "data": [
    {
      "playerId": 8478402,
      "playerName": "Connor McDavid",
      "teamAbbrevs": "EDM",
      "gamesPlayed": 82,
      "sprintBurstsPerGame": 3.2,
      "topSpeed": 25.4
    },
    {
      "playerId": 8477492,
      "playerName": "Nathan MacKinnon",
      "teamAbbrevs": "COL",
      "gamesPlayed": 80,
      "sprintBurstsPerGame": 2.8,
      "topSpeed": 24.1
    }
  ],
  "total": 2
}
```

- [ ] **Step 3.2: Write failing tests**

Create `apps/api/tests/scrapers/test_nhl_edge.py`:

```python
"""TDD tests for scrapers/nhl_edge.py. All HTTP and DB I/O is mocked."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from scrapers.nhl_edge import NhlEdgeScraper

FIXTURE = Path(__file__).parent / "fixtures" / "nhl_edge_sample.json"
SEASON = "2024-25"

_PLAYERS = [
    {"id": "p-mcdavid", "name": "Connor McDavid"},
    {"id": "p-mackinnon", "name": "Nathan MacKinnon"},
]
_ALIASES: list[dict] = []


def _make_response(data: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, text=json.dumps(data), request=httpx.Request("GET", "http://x"))


def _mock_db() -> MagicMock:
    db = MagicMock()
    db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "p-1"}]
    return db


class TestSeasonId:
    def test_2024_25(self) -> None:
        assert NhlEdgeScraper._season_id("2024-25") == "20242025"

    def test_2005_06(self) -> None:
        assert NhlEdgeScraper._season_id("2005-06") == "20052006"


class TestParseResponse:
    def test_returns_two_rows(self) -> None:
        data = json.loads(FIXTURE.read_text())["data"]
        assert len(NhlEdgeScraper._parse_response(data)) == 2

    def test_parses_speed_bursts(self) -> None:
        rows = NhlEdgeScraper._parse_response(json.loads(FIXTURE.read_text())["data"])
        mcdavid = next(r for r in rows if "McDavid" in r["player_name"])
        assert mcdavid["speed_bursts_22"] == pytest.approx(3.2)

    def test_parses_top_speed(self) -> None:
        rows = NhlEdgeScraper._parse_response(json.loads(FIXTURE.read_text())["data"])
        mcdavid = next(r for r in rows if "McDavid" in r["player_name"])
        assert mcdavid["top_speed"] == pytest.approx(25.4)

    def test_skips_row_with_no_name(self) -> None:
        assert NhlEdgeScraper._parse_response([{"playerName": ""}]) == []


class TestScrape:
    @pytest.mark.asyncio
    async def test_returns_count(self) -> None:
        scraper = NhlEdgeScraper()
        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(scraper, "_get_with_retry", new=AsyncMock(return_value=_make_response(json.loads(FIXTURE.read_text())))),
            patch.object(scraper, "_fetch_players", return_value=_PLAYERS),
            patch.object(scraper, "_fetch_aliases", return_value=_ALIASES),
        ):
            assert await scraper.scrape(SEASON, _mock_db()) == 2

    @pytest.mark.asyncio
    async def test_robots_disallowed_raises(self) -> None:
        from scrapers.base import RobotsDisallowedError
        scraper = NhlEdgeScraper()
        with patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=False)):
            with pytest.raises(RobotsDisallowedError):
                await scraper.scrape(SEASON, _mock_db())

    @pytest.mark.asyncio
    async def test_upserts_speed_columns(self) -> None:
        scraper = NhlEdgeScraper()
        upserted: list[dict] = []

        def capture(payload, on_conflict=None):
            upserted.append(payload)
            m = MagicMock()
            m.execute.return_value.data = [{"id": "p-1"}]
            return m

        db = _mock_db()
        db.table.return_value.upsert.side_effect = capture

        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(scraper, "_get_with_retry", new=AsyncMock(return_value=_make_response(json.loads(FIXTURE.read_text())))),
            patch.object(scraper, "_fetch_players", return_value=_PLAYERS),
            patch.object(scraper, "_fetch_aliases", return_value=_ALIASES),
        ):
            await scraper.scrape(SEASON, db)

        assert any("speed_bursts_22" in p for p in upserted)
        assert any("top_speed" in p for p in upserted)
```

Run: `cd apps/api && pytest tests/scrapers/test_nhl_edge.py -v`
Expected: **ImportError** (file doesn't exist yet).

- [ ] **Step 3.3: Implement `NhlEdgeScraper`**

Create `apps/api/scrapers/nhl_edge.py`:

```python
"""
NHL EDGE skating stats scraper.

Fetches speed burst counts and top speed from the NHL Stats API and upserts
``speed_bursts_22`` and ``top_speed`` into ``player_stats``.

No API key required. Free public endpoint.

IMPORTANT: Verify ``sprintBurstsPerGame`` and ``topSpeed`` field names against
the live API before finalising _parse_response. Update the fixture too.
"""
from __future__ import annotations

import logging
from typing import Any

from scrapers.base import BaseScraper, RobotsDisallowedError
from scrapers.matching import PlayerMatcher

logger = logging.getLogger(__name__)

_BASE_URL = (
    "https://api.nhle.com/stats/rest/en/skater/skating"
    "?isAggregate=true&isGame=false"
    "&start={start}&limit=100"
    "&cayenneExp=seasonId%3D{season_id}"
)
_PAGE_SIZE = 100


class NhlEdgeScraper(BaseScraper):
    """Scrapes NHL EDGE for speed burst and top speed stats (Tier 3)."""

    @staticmethod
    def _season_id(season: str) -> str:
        """'2024-25' → '20242025'"""
        left, right = season.split("-")
        year1 = int(left)
        year2 = year1 + 1
        return f"{year1}{year2}"

    @staticmethod
    def _parse_response(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = []
        for item in data:
            player_name = item.get("playerName", "")
            if not player_name:
                continue
            rows.append({
                "player_name": player_name,
                "speed_bursts_22": item.get("sprintBurstsPerGame"),
                "top_speed": item.get("topSpeed"),
            })
        return rows

    def _fetch_players(self, db: Any) -> list[dict[str, Any]]:
        return db.table("players").select("id,name").execute().data or []

    def _fetch_aliases(self, db: Any) -> list[dict[str, Any]]:
        return db.table("player_aliases").select("alias_name,player_id,source").execute().data or []

    def _upsert_player_stats(
        self, db: Any, player_id: str, season: str, stats: dict[str, Any]
    ) -> None:
        db.table("player_stats").upsert(
            {"player_id": player_id, "season": season, **stats},
            on_conflict="player_id,season",
        ).execute()

    async def scrape(self, season: str, db: Any) -> int:
        season_id = self._season_id(season)
        url0 = _BASE_URL.format(start=0, season_id=season_id)

        if not await self._check_robots_txt(url0):
            raise RobotsDisallowedError("robots.txt disallows NHL EDGE scraping")

        players = self._fetch_players(db)
        aliases = self._fetch_aliases(db)
        matcher = PlayerMatcher(players=players, aliases=aliases)

        start = 0
        count = 0
        while True:
            url = _BASE_URL.format(start=start, season_id=season_id)
            response = await self._get_with_retry(url)
            data = response.json().get("data", [])
            if not data:
                break

            for row in self._parse_response(data):
                player_id = matcher.resolve(row["player_name"])
                if player_id is None:
                    continue
                stats = {k: v for k, v in row.items() if k != "player_name" and v is not None}
                if stats:
                    self._upsert_player_stats(db, player_id, season, stats)
                    count += 1

            if len(data) < _PAGE_SIZE:
                break
            start += _PAGE_SIZE

        logger.info("NHL EDGE: upserted %d rows for %s", count, season)
        return count
```

- [ ] **Step 3.4: Run tests — all should pass**

```bash
cd apps/api && pytest tests/scrapers/test_nhl_edge.py -v
```
Expected: all green.

- [ ] **Step 3.5: Run full suite**

```bash
cd apps/api && pytest --tb=short -q
```

- [ ] **Step 3.6: Commit**

```bash
git add apps/api/scrapers/nhl_edge.py \
        apps/api/tests/scrapers/test_nhl_edge.py \
        apps/api/tests/scrapers/fixtures/nhl_edge_sample.json
git commit -m "feat(phase3a): add NHL EDGE scraper (speed_bursts_22, top_speed) [Tier 3]"
```

---

## Task 4: GitHub Actions Cron Updates

**Two workflows to update:**

1. **`retrain-trends.yml`** — add Hockey Reference scraper (runs annually, correct home for a stat-backfill scraper per the spec §3e)
2. **`scrape-projections.yml`** — add Elite Prospects and NHL EDGE (weekly cadence; EP flags need regular refresh as contracts evolve)

**Invocation style:** Use `python -m scrapers.X` (module invocation) consistent with the existing workflow. Each scraper module needs a `_main()` entry point and `if __name__ == "__main__"` block (see `nhl_com.py` for the pattern).

---

- [ ] **Step 4.1: Add `_main()` entry points to new scrapers**

Each new scraper needs the same entry point pattern used in `nhl_com.py`. Add to the bottom of each file:

**`hockey_reference.py`:**
```python
async def _main() -> None:
    from core.config import settings
    from supabase import create_client

    db = create_client(settings.supabase_url, settings.supabase_service_role_key)
    scraper = HockeyReferenceScraper()
    count = await scraper.scrape(settings.current_season, db)
    print(f"Hockey Reference: {count} rows upserted for {settings.current_season}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(_main())
```

**`elite_prospects.py`:**
```python
async def _main() -> None:
    from core.config import settings
    from supabase import create_client

    if not settings.elite_prospects_api_key:
        print("ELITE_PROSPECTS_API_KEY not set — skipping")
        return
    db = create_client(settings.supabase_url, settings.supabase_service_role_key)
    scraper = EliteProspectsScraper(api_key=settings.elite_prospects_api_key)
    count = await scraper.scrape(settings.current_season, db)
    print(f"Elite Prospects: {count} rows upserted for {settings.current_season}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(_main())
```

**`nhl_edge.py`:**
```python
async def _main() -> None:
    from core.config import settings
    from supabase import create_client

    db = create_client(settings.supabase_url, settings.supabase_service_role_key)
    scraper = NhlEdgeScraper()
    count = await scraper.scrape(settings.current_season, db)
    print(f"NHL EDGE: {count} rows upserted for {settings.current_season}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(_main())
```

- [ ] **Step 4.2: Add Hockey Reference step to `retrain-trends.yml`**

Open `.github/workflows/retrain-trends.yml`. If the file doesn't exist yet, create it with a job-level `defaults.run.working-directory: apps/api` (matches the pattern in `scrape-projections.yml`). Add the scraper step:

```yaml
# If creating retrain-trends.yml from scratch, include this at job level:
defaults:
  run:
    working-directory: apps/api

# Then add the step:
- name: Run Hockey Reference scraper (career SH%, experience)
  env:
    SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
    SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
  run: python -m scrapers.hockey_reference
```

> Note: Do NOT add `working-directory: apps/api` inline on the step — set it at job level via `defaults.run.working-directory` instead (consistent with `scrape-projections.yml`).

- [ ] **Step 4.3: Add EP + NHL EDGE steps to `scrape-projections.yml`**

After the `Scrape NST` step, add:

```yaml
- name: Scrape Elite Prospects (ELC + contract year flags)
  env:
    SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
    SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
    ELITE_PROSPECTS_API_KEY: ${{ secrets.ELITE_PROSPECTS_API_KEY }}
  run: python -m scrapers.elite_prospects

- name: Scrape NHL EDGE (speed stats — Tier 3)
  env:
    SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
    SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
  run: python -m scrapers.nhl_edge
```

- [ ] **Step 4.4: Commit**

```bash
git add .github/workflows/retrain-trends.yml \
        .github/workflows/scrape-projections.yml \
        apps/api/scrapers/hockey_reference.py \
        apps/api/scrapers/elite_prospects.py \
        apps/api/scrapers/nhl_edge.py
git commit -m "chore(phase3a): add new scrapers to GitHub Actions cron workflows"
```

---

## Task 5: Final Verification and Docs

- [ ] **Step 5.1: Run full test suite**

```bash
cd apps/api && pytest --tb=short -q
```
Expected: 571 existing + ~40 new tests, all green.

- [ ] **Step 5.2: Lint**

```bash
cd apps/api && ruff check . && ruff format --check .
```

- [ ] **Step 5.3: Update `apps/api/CLAUDE.md`**

In the Phase 3b Scraper Verification table, add:

```
| Hockey Reference (sh_pct_career_avg, nhl_experience) | ✅ Complete | HockeyReferenceScraper; scrape_history() for backfill |
| Elite Prospects (elc_flag, contract_year_flag)       | ✅ Complete | EliteProspectsScraper; needs ELITE_PROSPECTS_API_KEY secret |
| NHL EDGE (speed_bursts_22, top_speed)                | ✅ Complete | NhlEdgeScraper; Tier 3, optional |
| Evolving Hockey (gar, xgar)                          | 🔁 Manual  | No scraper — manual CSV upload via POST /sources/upload; $5 one-time pull |
```

- [ ] **Step 5.4: Update `docs/backend-reference.md`**

Find the scrapers section and add entries for the three new scrapers:

```markdown
### Hockey Reference (`scrapers/hockey_reference.py`)
- **Table:** `player_stats`
- **Columns:** `sh_pct_career_avg` (float, rolling career SH%), `nhl_experience` (int, seasons with GP>0), `career_goals` (int), `career_shots` (int)
- **Frequency:** Annual (retraining cron) — `scrape_history("2005-06", current_season, db)` for initial backfill; `scrape(season, db)` for yearly updates
- **Rate limit:** `Crawl-delay: 3` per robots.txt — `MIN_DELAY_SECONDS = 3.0`

### Elite Prospects (`scrapers/elite_prospects.py`)
- **Table:** `player_stats`
- **Columns:** `elc_flag` (bool), `contract_year_flag` (bool)
- **Frequency:** Weekly via `scrape-projections.yml`
- **Requires:** `ELITE_PROSPECTS_API_KEY` env var (free tier at eliteprospects.com/api)

### NHL EDGE (`scrapers/nhl_edge.py`) — Tier 3, Optional
- **Table:** `player_stats`
- **Columns:** `speed_bursts_22` (float), `top_speed` (float)
- **Frequency:** Weekly via `scrape-projections.yml`
```

- [ ] **Step 5.5: Push and open PR**

```bash
git push origin feat/3a-scrapers
gh pr create \
  --title "feat(phase3a): add Hockey Reference, Elite Prospects, and NHL EDGE scrapers" \
  --body "$(cat <<'EOF'
## Summary

- Adds `HockeyReferenceScraper` — populates `sh_pct_career_avg` (Tier 1) and `nhl_experience` (Tier 2); `scrape_history()` for one-time backfill of 2005-06 through 2024-25; `scrape()` for annual updates; respects 3s crawl delay
- Adds `EliteProspectsScraper` — populates `elc_flag` and `contract_year_flag` (Tier 3); requires `ELITE_PROSPECTS_API_KEY` GitHub Secret
- Adds `NhlEdgeScraper` — populates `speed_bursts_22` and `top_speed` (Tier 3, optional); free NHL API
- Updates `retrain-trends.yml` with Hockey Reference step; `scrape-projections.yml` with EP + EDGE steps
- **Evolving Hockey (gar/xgar):** manual CSV upload only per spec decision; no scraper

## Test Plan

- All scraper tests follow the `NstScraper` TDD pattern (mocked HTTP + DB, HTML/JSON fixtures)
- `pytest tests/scrapers/test_hockey_reference.py` — covers `_parse_html`, `_compute_career_stats`, `scrape()` with/without prior DB career data, `scrape_history()`
- `pytest tests/scrapers/test_elite_prospects.py` — covers `_parse_response`, pagination, missing API key, robots.txt
- `pytest tests/scrapers/test_nhl_edge.py` — covers `_parse_response`, speed columns upsert
- Full suite: `pytest --tb=short -q` — all green

## Follow-up Tasks

- Add `ELITE_PROSPECTS_API_KEY` to GitHub Secrets (repo settings)
- Run one-time backfill: `python -c "import asyncio; from scrapers.hockey_reference import HockeyReferenceScraper; ..."` with `scrape_history("2005-06", "2024-25", db)`
- Verify EP + NHL EDGE field names against live API and update `_parse_response` + fixtures if needed
- Add `career_goals` and `career_shots` columns to DB migration (needed by `HockeyReferenceScraper._upsert_player_stats`)
EOF
)"
```

---

## Notes for Implementer

1. **`PlayerMatcher` API** — constructor is `PlayerMatcher(players=list[dict], aliases=list[dict])`, method is `matcher.resolve(raw_name)`. Always call `_fetch_players(db)` and `_fetch_aliases(db)` first. Never pass `db` to the constructor.

2. **`career_goals` / `career_shots` migration** — `HockeyReferenceScraper` stores raw career totals so that the incremental `scrape()` can correctly accumulate without re-fetching all history. Before running, apply: `ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS career_goals integer; ALTER TABLE player_stats ADD COLUMN IF NOT EXISTS career_shots integer;`

3. **EP field names** — make one real API call before finalising. The fixture uses educated guesses. Update `_parse_response` and `elite_prospects_sample.json` to match actual response.

4. **NHL EDGE field names** — same caveat for `sprintBurstsPerGame` and `topSpeed`.

5. **One-time Hockey Reference backfill** — run after merging:
   ```python
   scraper = HockeyReferenceScraper()
   await scraper.scrape_history("2005-06", "2024-25", db)
   ```
   This takes ~60s (20 pages × 3s crawl delay). Run manually, not via cron.

6. **`retrain-trends.yml` may not exist yet** — it was defined in the Phase 3e spec but not yet created. If it doesn't exist, create it as a minimal workflow stub and add it to the PR.

7. **Live smoke test deferred** — Supabase branching (isolated dev environments) is a Pro feature. The free-tier account does not support it, so the live end-to-end smoke test was skipped for this PR. At the end of Phase 3, before the feature-engineering pipeline and model training work begins, add a local Supabase CLI stack as a new task:

   **End-of-Phase-3 task: Local Supabase dev stack for smoke testing**
   ```
   - Install Supabase CLI: brew install supabase/tap/supabase
   - supabase init  (from repo root, creates supabase/config.toml)
   - supabase start  (spins up local Postgres + Auth + REST on localhost:54321)
   - supabase db push  (applies all migrations from supabase/migrations/)
   - Set SUPABASE_URL=http://localhost:54321 and SUPABASE_SERVICE_ROLE_KEY=<local key>
     in apps/api/.env (printed by `supabase start`)
   - Run each scraper manually against the local instance:
       python -m scrapers.nhl_com
       python -m scrapers.moneypuck
       python -m scrapers.nst
       python -m scrapers.hockey_reference
       python -m scrapers.elite_prospects    # needs ELITE_PROSPECTS_API_KEY
       python -m scrapers.nhl_edge
   - Verify rows written: supabase db query "SELECT COUNT(*) FROM player_stats WHERE season='2024-25'"
   - supabase stop  (tears down containers)
   ```
   This gives a free, reproducible, isolated environment for smoke testing any scraper or migration before merging to main.
