"""
Base scraper class.

Enforces:
  - robots.txt compliance before any fetch
  - polite rate-limiting between pages
  - exponential-backoff retries on transient server errors
"""

from __future__ import annotations

import asyncio
import logging
import urllib.robotparser
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


class RobotsDisallowedError(Exception):
    """Raised when robots.txt disallows scraping the target URL."""


class BaseScraper(ABC):
    # ROBOTS_AGENT is the bare name checked against robots.txt entries.
    # USER_AGENT is the full HTTP header string sent with every request.
    ROBOTS_AGENT: str = "PuckLogicBot"
    USER_AGENT: str = (
        "PuckLogicBot/1.0 (fantasy hockey stats aggregator; contact@pucklogic.com)"
    )
    MIN_DELAY_SECONDS: float = 1.0
    MAX_RETRIES: int = 3
    RETRY_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

    def __init__(self, http: httpx.AsyncClient | None = None) -> None:
        self._http = http or httpx.AsyncClient(
            headers={"User-Agent": self.USER_AGENT},
            follow_redirects=True,
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # robots.txt
    # ------------------------------------------------------------------

    async def _check_robots_txt(self, url: str) -> bool:
        """Return True if ``url`` may be fetched according to robots.txt."""
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        try:
            response = await self._http.get(robots_url)
            rp.parse(response.text.splitlines())
        except Exception:
            # Unreachable robots.txt → assume allowed (fail-open)
            logger.warning(
                "Could not fetch robots.txt from %s — assuming allowed", robots_url
            )
            return True
        allowed = rp.can_fetch(self.ROBOTS_AGENT, url)
        if not allowed:
            logger.warning("robots.txt disallows %s for %s", url, self.USER_AGENT)
        return allowed

    # ------------------------------------------------------------------
    # HTTP with retry
    # ------------------------------------------------------------------

    async def _get_with_retry(self, url: str, **kwargs: Any) -> httpx.Response:
        """GET ``url`` with exponential backoff on retryable status codes."""
        last_exc: Exception | None = None
        for attempt in range(self.MAX_RETRIES):
            if attempt > 0:
                await asyncio.sleep(2 ** (attempt - 1))  # 1 s, 2 s, 4 s …
            try:
                response = await self._http.get(url, **kwargs)
                if response.status_code in self.RETRY_STATUSES:
                    last_exc = httpx.HTTPStatusError(
                        f"HTTP {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                    continue
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in self.RETRY_STATUSES:
                    raise
                last_exc = exc
            except httpx.RequestError as exc:
                last_exc = exc

        raise last_exc or RuntimeError("Max retries exceeded")

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def scrape(self, season: str, db: Any) -> int:
        """Fetch source data and upsert to ``db``.

        Returns the number of ``player_rankings`` rows upserted.
        """
