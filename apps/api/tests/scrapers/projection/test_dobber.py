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

    def test_skips_blank_player_name(self) -> None:
        csv_text = "Player,G,A\n,10,20\nConnor McDavid,52,72\n"
        rows = DobberScraper._parse_csv(csv_text)
        assert len(rows) == 1


class TestIngest:
    def test_returns_matched_count(self, mock_db: MagicMock) -> None:
        # Need players + aliases to be returned on select calls
        call_results = [PLAYERS, ALIASES]
        call_iter = iter(call_results)

        def select_side_effect(*args, **kwargs):
            m = MagicMock()
            try:
                m.execute.return_value.data = next(call_iter)
            except StopIteration:
                m.execute.return_value.data = []
            return m

        mock_db.table.return_value.select.side_effect = select_side_effect

        scraper = DobberScraper()
        count = scraper.ingest(FIXTURE_CSV.read_text(), "2025-26", mock_db)
        # McDavid + Draisaitl matched; Unknown Player skipped
        assert count == 2


class TestScrape:
    @pytest.mark.asyncio
    async def test_scrape_raises_not_implemented(self, mock_db: MagicMock) -> None:
        scraper = DobberScraper()
        with pytest.raises(NotImplementedError):
            await scraper.scrape("2025-26", mock_db)
