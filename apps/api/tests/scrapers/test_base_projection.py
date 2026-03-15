from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scrapers.base_projection import BaseProjectionScraper


class ConcreteProjectionScraper(BaseProjectionScraper):
    SOURCE_NAME = "test_source"
    DISPLAY_NAME = "Test Source"

    async def scrape(self, season: str, db: object) -> int:
        return 0


class TestBaseProjectionScraperContract:
    def test_source_name_required(self) -> None:
        scraper = ConcreteProjectionScraper()
        assert scraper.SOURCE_NAME == "test_source"

    def test_display_name_required(self) -> None:
        scraper = ConcreteProjectionScraper()
        assert scraper.DISPLAY_NAME == "Test Source"

    def test_missing_source_name_raises(self) -> None:
        with pytest.raises(TypeError):
            class BadScraper(BaseProjectionScraper):
                DISPLAY_NAME = "Bad"
                # SOURCE_NAME missing — abstract attr

                async def scrape(self, season: str, db: object) -> int:
                    return 0
            BadScraper()

    def test_missing_scrape_raises(self) -> None:
        with pytest.raises(TypeError):
            class BadScraper(BaseProjectionScraper):
                SOURCE_NAME = "x"
                DISPLAY_NAME = "X"
                # scrape() not implemented
            BadScraper()

    @pytest.mark.asyncio
    async def test_scrape_returns_int(self) -> None:
        scraper = ConcreteProjectionScraper()
        result = await scraper.scrape("2025-26", MagicMock())
        assert isinstance(result, int)
