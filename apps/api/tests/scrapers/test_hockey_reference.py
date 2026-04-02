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
        db.table.return_value.select.return_value.lt.return_value.execute.return_value.data = (
            prior_data
        )
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

    def test_traded_player_dedups_to_highest_gp_row(self) -> None:
        html = """
        <table id="player_stats">
          <tbody>
            <tr>
              <td data-stat="name_display">Traded Player</td>
              <td data-stat="games">50</td>
              <td data-stat="goals">20</td>
              <td data-stat="shots">150</td>
            </tr>
            <tr>
              <td data-stat="name_display">Traded Player</td>
              <td data-stat="games">20</td>
              <td data-stat="goals">8</td>
              <td data-stat="shots">70</td>
            </tr>
            <tr>
              <td data-stat="name_display">Traded Player</td>
              <td data-stat="games">30</td>
              <td data-stat="goals">12</td>
              <td data-stat="shots">80</td>
            </tr>
            <tr>
              <td data-stat="name_display">Single Team</td>
              <td data-stat="games">82</td>
              <td data-stat="goals">25</td>
              <td data-stat="shots">200</td>
            </tr>
          </tbody>
        </table>
        """
        rows = HockeyReferenceScraper._parse_html(html)

        traded = [r for r in rows if r["player_name"] == "Traded Player"]
        assert len(traded) == 1
        assert traded[0]["gp"] == 50
        assert traded[0]["goals"] == 20
        assert traded[0]["shots"] == 150

    def test_traded_player_equal_gp_keeps_first_row(self) -> None:
        html = """
        <table id="player_stats">
          <tbody>
            <tr>
              <td data-stat="name_display">Equal GP Player</td>
              <td data-stat="games">40</td>
              <td data-stat="goals">10</td>
              <td data-stat="shots">100</td>
            </tr>
            <tr>
              <td data-stat="name_display">Equal GP Player</td>
              <td data-stat="games">40</td>
              <td data-stat="goals">12</td>
              <td data-stat="shots">110</td>
            </tr>
          </tbody>
        </table>
        """
        rows = HockeyReferenceScraper._parse_html(html)

        assert len(rows) == 1
        assert rows[0]["player_name"] == "Equal GP Player"
        assert rows[0]["goals"] == 10
        assert rows[0]["shots"] == 100


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

    def test_career_stats_correct_after_single_season_dedup(self) -> None:
        rows = {
            "2023-24": [{"player_name": "P", "goals": 10, "shots": 100, "gp": 70}],
            # Simulates output after parser dedup keeps the aggregate row only.
            "2024-25": [{"player_name": "P", "goals": 20, "shots": 150, "gp": 50}],
        }
        result = HockeyReferenceScraper._compute_career_stats(rows)
        assert result["P"]["2024-25"]["career_goals"] == 30
        assert result["P"]["2024-25"]["career_shots"] == 250
        assert result["P"]["2024-25"]["sh_pct_career_avg"] == pytest.approx(30 / 250)


# ---------------------------------------------------------------------------
# scrape() — single-season path, uses DB for prior career context
# ---------------------------------------------------------------------------


class TestScrape:
    @pytest.mark.asyncio
    async def test_returns_upserted_count(self) -> None:
        scraper = HockeyReferenceScraper()
        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(
                scraper,
                "_get_with_retry",
                new=AsyncMock(return_value=_make_response(FIXTURE.read_text())),
            ),
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
            patch.object(
                scraper,
                "_get_with_retry",
                new=AsyncMock(return_value=_make_response(FIXTURE.read_text())),
            ),
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
            patch.object(
                scraper,
                "_get_with_retry",
                new=AsyncMock(return_value=_make_response(FIXTURE.read_text())),
            ),
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
            patch.object(
                scraper,
                "_get_with_retry",
                new=AsyncMock(return_value=_make_response(FIXTURE.read_text())),
            ),
            patch.object(scraper, "_fetch_players", return_value=[]),  # no players → no matches
            patch.object(scraper, "_fetch_aliases", return_value=[]),
        ):
            count = await scraper.scrape(SEASON, db)
        db.table.return_value.upsert.assert_not_called()
        assert count == 0


# ---------------------------------------------------------------------------
# scrape_history() — multi-season backfill
# ---------------------------------------------------------------------------


class TestScrapeHistory:
    @pytest.mark.asyncio
    async def test_robots_disallowed_raises(self) -> None:
        from scrapers.base import RobotsDisallowedError

        scraper = HockeyReferenceScraper()
        with patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=False)):
            with pytest.raises(RobotsDisallowedError):
                await scraper.scrape_history("2023-24", "2024-25", _mock_db())

    @pytest.mark.asyncio
    async def test_returns_upsert_count(self) -> None:
        """Two seasons × 3 players in fixture = 6 upserted rows."""
        scraper = HockeyReferenceScraper()
        fixture_html = FIXTURE.read_text()
        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(
                scraper,
                "_get_with_retry",
                new=AsyncMock(
                    side_effect=[
                        _make_response(fixture_html),
                        _make_response(fixture_html),
                    ]
                ),
            ),
            patch.object(scraper, "_fetch_players", return_value=_PLAYERS),
            patch.object(scraper, "_fetch_aliases", return_value=_ALIASES),
        ):
            count = await scraper.scrape_history("2023-24", "2024-25", _mock_db())
        assert count == 6  # 2 seasons × 3 players

    @pytest.mark.asyncio
    async def test_sleeps_between_pages(self) -> None:
        """asyncio.sleep must be called between season fetches to honour crawl-delay."""
        scraper = HockeyReferenceScraper()
        fixture_html = FIXTURE.read_text()
        with (
            patch.object(scraper, "_check_robots_txt", new=AsyncMock(return_value=True)),
            patch.object(
                scraper,
                "_get_with_retry",
                new=AsyncMock(
                    side_effect=[
                        _make_response(fixture_html),
                        _make_response(fixture_html),
                    ]
                ),
            ),
            patch.object(scraper, "_fetch_players", return_value=_PLAYERS),
            patch.object(scraper, "_fetch_aliases", return_value=_ALIASES),
            patch("scrapers.hockey_reference.asyncio.sleep", new=AsyncMock()) as mock_sleep,
        ):
            await scraper.scrape_history("2023-24", "2024-25", _mock_db())
        # 2 seasons → sleep once between them (not after the last)
        mock_sleep.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_computes_career_totals_across_seasons(self) -> None:
        """scrape_history accumulates career stats without reading the DB."""
        scraper = HockeyReferenceScraper()
        fixture_html = FIXTURE.read_text()
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
            patch.object(
                scraper,
                "_get_with_retry",
                # Same fixture for both seasons → each player appears twice
                new=AsyncMock(
                    side_effect=[
                        _make_response(fixture_html),
                        _make_response(fixture_html),
                    ]
                ),
            ),
            patch.object(scraper, "_fetch_players", return_value=_PLAYERS),
            patch.object(scraper, "_fetch_aliases", return_value=_ALIASES),
            patch("scrapers.hockey_reference.asyncio.sleep", new=AsyncMock()),
        ):
            await scraper.scrape_history("2023-24", "2024-25", db)

        # Fixture has McDavid at 32G/200S. Two identical seasons → 64G/400S cumulative
        # by the second season row.  Find the 2024-25 row for McDavid.
        mcdavid_rows = [p for p in upserted if p.get("player_id") == "p-mcdavid"]
        assert len(mcdavid_rows) == 2
        last = max(mcdavid_rows, key=lambda r: r["season"])
        assert last["career_goals"] == 64
        assert last["career_shots"] == 400
        assert last["nhl_experience"] == 2


# ---------------------------------------------------------------------------
# _main() entrypoint --history flag
# ---------------------------------------------------------------------------


class TestMain:
    """Verify the __main__ entrypoint dispatches to the correct scrape method."""

    @pytest.mark.asyncio
    async def test_history_flag_calls_scrape_history(self, monkeypatch):
        """python -m scrapers.hockey_reference --history must call scrape_history."""
        import sys
        from unittest.mock import AsyncMock, patch

        from scrapers.hockey_reference import HockeyReferenceScraper

        monkeypatch.setattr(sys, "argv", ["scrapers.hockey_reference", "--history"])

        mock_scraper = MagicMock(spec=HockeyReferenceScraper)
        mock_scraper.scrape_history = AsyncMock(return_value=42)

        with (
            patch("scrapers.hockey_reference.HockeyReferenceScraper", return_value=mock_scraper),
            patch("supabase.create_client"),
        ):
            from scrapers.hockey_reference import _main

            await _main()

        # Backfill must start at 2005-06, not 2008-09.
        # Labels start at 2008; the 2008 feature window needs rows for 2006 and 2007.
        mock_scraper.scrape_history.assert_called_once()
        call_args = mock_scraper.scrape_history.call_args
        assert call_args.args[0] == "2005-06", (
            f"History backfill must start at '2005-06', got '{call_args.args[0]}'"
        )
        mock_scraper.scrape.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_flag_calls_scrape(self, monkeypatch):
        """python -m scrapers.hockey_reference (no flags) must call scrape only."""
        import sys
        from unittest.mock import AsyncMock, patch

        from scrapers.hockey_reference import HockeyReferenceScraper

        monkeypatch.setattr(sys, "argv", ["scrapers.hockey_reference"])

        mock_scraper = MagicMock(spec=HockeyReferenceScraper)
        mock_scraper.scrape = AsyncMock(return_value=10)

        with (
            patch("scrapers.hockey_reference.HockeyReferenceScraper", return_value=mock_scraper),
            patch("supabase.create_client"),
        ):
            from scrapers.hockey_reference import _main

            await _main()

        mock_scraper.scrape.assert_called_once()
        mock_scraper.scrape_history.assert_not_called()
