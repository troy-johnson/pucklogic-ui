# apps/api/tests/scrapers/projection/test_apples_ginos.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scrapers.projection.apples_ginos import ApplesGinosScraper

FIXTURE_CSV = Path(__file__).parent.parent / "fixtures" / "apples_ginos_sample.csv"


@pytest.fixture
def mock_db() -> MagicMock:
    db = MagicMock()
    db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "src-1"}]
    db.table.return_value.select.return_value.execute.return_value.data = []
    return db


# ---------------------------------------------------------------------------
# Unit: _parse_csv
# ---------------------------------------------------------------------------


class TestParseCsv:
    def test_returns_rows_with_player_name(self) -> None:
        rows = ApplesGinosScraper._parse_csv(FIXTURE_CSV.read_text())
        assert len(rows) >= 2
        assert all("player_name" in r for r in rows)

    def test_maps_goals(self) -> None:
        rows = ApplesGinosScraper._parse_csv(FIXTURE_CSV.read_text())
        mcdavid = next(r for r in rows if r["player_name"] == "Connor McDavid")
        assert mcdavid.get("g") == 50

    def test_maps_assists(self) -> None:
        rows = ApplesGinosScraper._parse_csv(FIXTURE_CSV.read_text())
        mcdavid = next(r for r in rows if r["player_name"] == "Connor McDavid")
        assert mcdavid.get("a") == 74

    def test_maps_ppp(self) -> None:
        rows = ApplesGinosScraper._parse_csv(FIXTURE_CSV.read_text())
        draisaitl = next(r for r in rows if r["player_name"] == "Leon Draisaitl")
        assert draisaitl.get("ppp") == 29

    def test_maps_shots_on_goal(self) -> None:
        rows = ApplesGinosScraper._parse_csv(FIXTURE_CSV.read_text())
        mckinnon = next(r for r in rows if r["player_name"] == "Nathan MacKinnon")
        assert mckinnon.get("sog") == 248

    def test_maps_hits(self) -> None:
        rows = ApplesGinosScraper._parse_csv(FIXTURE_CSV.read_text())
        draisaitl = next(r for r in rows if r["player_name"] == "Leon Draisaitl")
        assert draisaitl.get("hits") == 42

    def test_maps_blocks(self) -> None:
        rows = ApplesGinosScraper._parse_csv(FIXTURE_CSV.read_text())
        mckinnon = next(r for r in rows if r["player_name"] == "Nathan MacKinnon")
        assert mckinnon.get("blocks") == 20

    def test_maps_gp(self) -> None:
        rows = ApplesGinosScraper._parse_csv(FIXTURE_CSV.read_text())
        mcdavid = next(r for r in rows if r["player_name"] == "Connor McDavid")
        assert mcdavid.get("gp") == 82

    def test_maps_pim(self) -> None:
        rows = ApplesGinosScraper._parse_csv(FIXTURE_CSV.read_text())
        draisaitl = next(r for r in rows if r["player_name"] == "Leon Draisaitl")
        assert draisaitl.get("pim") == 38

    def test_skips_rows_without_player_name(self) -> None:
        csv_with_blank = "Player,G,A\n,10,20\nConnor McDavid,50,74\n"
        rows = ApplesGinosScraper._parse_csv(csv_with_blank)
        assert all(r["player_name"] for r in rows)
        assert len(rows) == 1

    def test_drops_missing_stat_values(self) -> None:
        csv_with_dash = "Player,G,A\nConnor McDavid,-,74\n"
        rows = ApplesGinosScraper._parse_csv(csv_with_dash)
        assert len(rows) == 1
        assert "g" not in rows[0]
        assert rows[0].get("a") == 74


# ---------------------------------------------------------------------------
# Integration: ingest()
# ---------------------------------------------------------------------------


class TestIngest:
    def test_returns_int(self, mock_db: MagicMock) -> None:
        scraper = ApplesGinosScraper()
        count = scraper.ingest(FIXTURE_CSV.read_text(), "2025-26", mock_db)
        assert isinstance(count, int)
        assert count >= 0

    def test_zero_rows_when_no_players_in_db(self, mock_db: MagicMock) -> None:
        """With empty players table, all names are unmatched → 0 upserts."""
        scraper = ApplesGinosScraper()
        count = scraper.ingest(FIXTURE_CSV.read_text(), "2025-26", mock_db)
        assert count == 0

    def test_upserts_matched_players(self, mock_db: MagicMock) -> None:
        """When players table contains exact-match entries, upsert is called."""
        players = [
            {"id": "p1", "name": "Connor McDavid", "nhl_id": "8478402"},
            {"id": "p2", "name": "Leon Draisaitl", "nhl_id": "8477934"},
        ]
        scraper = ApplesGinosScraper()
        with patch(
            "scrapers.projection.apples_ginos.fetch_players_and_aliases",
            return_value=(players, []),
        ):
            count = scraper.ingest(FIXTURE_CSV.read_text(), "2025-26", mock_db)
        assert count == 2


# ---------------------------------------------------------------------------
# scrape() raises NotImplementedError
# ---------------------------------------------------------------------------


class TestScrape:
    @pytest.mark.asyncio
    async def test_scrape_raises_not_implemented(self, mock_db: MagicMock) -> None:
        scraper = ApplesGinosScraper()
        with pytest.raises(NotImplementedError):
            await scraper.scrape("2025-26", mock_db)
