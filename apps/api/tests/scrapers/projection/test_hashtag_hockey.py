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

    def test_goals_are_season_totals(self) -> None:
        """Goals should be GP * per-game rate, rounded to int — not raw rate."""
        html = FIXTURE_PATH.read_text(encoding="utf-8")
        rows = HashtagHockeyScraper()._parse_html(html)
        # Find MacKinnon: GP=17, G/gp=0.59 → 17 * 0.59 = 10.03 → 10
        mck = next((r for r in rows if "MacKinnon" in r["player_name"]), None)
        assert mck is not None
        assert mck.get("g") == 10  # round(17 * 0.59)

    def test_sog_are_season_totals(self) -> None:
        """SOG should be GP * per-game rate."""
        html = FIXTURE_PATH.read_text(encoding="utf-8")
        rows = HashtagHockeyScraper()._parse_html(html)
        mck = next((r for r in rows if "MacKinnon" in r["player_name"]), None)
        assert mck is not None
        assert mck.get("sog") == round(17 * 4.35)  # 74

    def test_skips_rows_with_no_player_name(self) -> None:
        html = FIXTURE_PATH.read_text(encoding="utf-8")
        rows = HashtagHockeyScraper()._parse_html(html)
        assert all(r["player_name"] for r in rows)

    def test_gp_stored_correctly(self) -> None:
        html = FIXTURE_PATH.read_text(encoding="utf-8")
        rows = HashtagHockeyScraper()._parse_html(html)
        mck = next((r for r in rows if "MacKinnon" in r["player_name"]), None)
        assert mck is not None
        assert mck.get("gp") == 17


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
            patch.object(
                scraper,
                "_get_with_retry",
                new=AsyncMock(return_value=MagicMock(text=html)),
            ),
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
