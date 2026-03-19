"""
TDD tests for scrapers/base.py.

All HTTP and DB I/O is mocked — no real network calls.
Written BEFORE the implementation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from scrapers.base import BaseScraper

# ---------------------------------------------------------------------------
# Minimal concrete subclass for testing
# ---------------------------------------------------------------------------


class _DummyScraper(BaseScraper):
    async def scrape(self, season: str, db) -> int:  # type: ignore[override]
        return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(status_code: int = 200, text: str = "") -> httpx.Response:
    return httpx.Response(status_code, text=text, request=httpx.Request("GET", "http://x"))


# ---------------------------------------------------------------------------
# robots.txt
# ---------------------------------------------------------------------------


class TestRobotsTxt:
    @pytest.mark.asyncio
    async def test_returns_true_when_permitted(self) -> None:
        robots_txt = "User-agent: *\nAllow: /"
        mock_http = AsyncMock()
        mock_http.get.return_value = _make_response(200, robots_txt)
        scraper = _DummyScraper(http=mock_http)
        assert await scraper._check_robots_txt("https://example.com/data") is True

    @pytest.mark.asyncio
    async def test_returns_false_when_disallowed(self) -> None:
        robots_txt = "User-agent: *\nDisallow: /"
        mock_http = AsyncMock()
        mock_http.get.return_value = _make_response(200, robots_txt)
        scraper = _DummyScraper(http=mock_http)
        assert await scraper._check_robots_txt("https://example.com/data") is False

    @pytest.mark.asyncio
    async def test_returns_true_when_robots_txt_unreachable(self) -> None:
        """Network failure on robots.txt → assume allowed (fail-open)."""
        mock_http = AsyncMock()
        mock_http.get.side_effect = httpx.RequestError("timeout")
        scraper = _DummyScraper(http=mock_http)
        assert await scraper._check_robots_txt("https://example.com/data") is True

    @pytest.mark.asyncio
    async def test_fetches_robots_from_root_domain(self) -> None:
        """Must fetch /robots.txt from the root domain, not the target path."""
        mock_http = AsyncMock()
        mock_http.get.return_value = _make_response(200, "User-agent: *\nAllow: /")
        scraper = _DummyScraper(http=mock_http)
        await scraper._check_robots_txt("https://api.example.com/stats/rest/en/skater")
        called_url = mock_http.get.call_args.args[0]
        assert called_url == "https://api.example.com/robots.txt"

    @pytest.mark.asyncio
    async def test_robots_agent_name_matches_check(self) -> None:
        """ROBOTS_AGENT (bare name) must be used for can_fetch(),
        not the full UA string."""
        robots_txt = f"User-agent: {_DummyScraper.ROBOTS_AGENT}\nDisallow: /"
        mock_http = AsyncMock()
        mock_http.get.return_value = _make_response(200, robots_txt)
        scraper = _DummyScraper(http=mock_http)
        assert await scraper._check_robots_txt("https://example.com/data") is False


# ---------------------------------------------------------------------------
# _get_with_retry
# ---------------------------------------------------------------------------


class TestGetWithRetry:
    @pytest.mark.asyncio
    async def test_returns_response_on_success(self) -> None:
        mock_http = AsyncMock()
        mock_http.get.return_value = _make_response(200, '{"data": []}')
        scraper = _DummyScraper(http=mock_http)
        resp = await scraper._get_with_retry("https://example.com/api")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_retries_on_429(self) -> None:
        mock_http = AsyncMock()
        mock_http.get.side_effect = [
            _make_response(429),
            _make_response(200, "ok"),
        ]
        scraper = _DummyScraper(http=mock_http)
        with patch("scrapers.base.asyncio.sleep", new_callable=AsyncMock):
            resp = await scraper._get_with_retry("https://example.com/api")
        assert resp.status_code == 200
        assert mock_http.get.call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_500(self) -> None:
        mock_http = AsyncMock()
        mock_http.get.side_effect = [
            _make_response(500),
            _make_response(200, "ok"),
        ]
        scraper = _DummyScraper(http=mock_http)
        with patch("scrapers.base.asyncio.sleep", new_callable=AsyncMock):
            resp = await scraper._get_with_retry("https://example.com/api")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self) -> None:
        mock_http = AsyncMock()
        mock_http.get.return_value = _make_response(503)
        scraper = _DummyScraper(http=mock_http)
        with (
            patch("scrapers.base.asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(Exception),
        ):
            await scraper._get_with_retry("https://example.com/api")
        assert mock_http.get.call_count == scraper.MAX_RETRIES

    @pytest.mark.asyncio
    async def test_does_not_retry_on_404(self) -> None:
        """404 is not a retryable status — should raise immediately."""
        req = httpx.Request("GET", "https://example.com/api")
        mock_http = AsyncMock()
        mock_http.get.side_effect = httpx.HTTPStatusError(
            "Not Found", request=req, response=httpx.Response(404, request=req)
        )
        scraper = _DummyScraper(http=mock_http)
        with pytest.raises(httpx.HTTPStatusError):
            await scraper._get_with_retry("https://example.com/api")
        assert mock_http.get.call_count == 1

    @pytest.mark.asyncio
    async def test_sleep_uses_exponential_backoff(self) -> None:
        """Sleep durations should double each retry: 1s, 2s."""
        mock_http = AsyncMock()
        mock_http.get.side_effect = [
            _make_response(503),
            _make_response(503),
            _make_response(200, "ok"),
        ]
        scraper = _DummyScraper(http=mock_http)
        sleep_calls = []

        async def mock_sleep(s: float) -> None:
            sleep_calls.append(s)

        with patch("scrapers.base.asyncio.sleep", side_effect=mock_sleep):
            await scraper._get_with_retry("https://example.com/api")
        assert sleep_calls == [1, 2]
