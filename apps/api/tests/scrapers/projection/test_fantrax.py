# apps/api/tests/scrapers/projection/test_fantrax.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scrapers.projection.fantrax import FantraxScraper


class TestScrape:
    @pytest.mark.asyncio
    async def test_returns_int(self, monkeypatch) -> None:
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "src-1"}]
        mock_db.table.return_value.select.return_value.execute.return_value.data = []

        scraper = FantraxScraper()
        monkeypatch.setattr("core.config.settings.fantrax_session_token", "tok")
        monkeypatch.setattr(scraper, "_check_robots_txt", AsyncMock(return_value=True))
        with patch.object(scraper, "_fetch_fantrax_players", new=AsyncMock(return_value=[])):
            count = await scraper.scrape("2025-26", mock_db)
        assert isinstance(count, int)
        assert count == 0

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
