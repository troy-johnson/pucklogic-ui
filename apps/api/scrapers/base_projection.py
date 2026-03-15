"""
Abstract base class for projection-source scrapers.

Separate from BaseScraper (which writes to player_stats).
All projection scrapers — auto-scraped and user-uploaded — implement this ABC.
HTTP helpers (robots.txt, retry) are inherited from BaseScraper where needed;
import BaseScraper in your concrete class if you need network access.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseProjectionScraper(ABC):
    """Scrapes or parses a projection source and writes rows to player_projections.

    Class attributes that concrete scrapers MUST define:
        SOURCE_NAME   — machine key matching sources.name (e.g. "hashtag_hockey")
        DISPLAY_NAME  — human label (e.g. "Hashtag Hockey")
    """

    SOURCE_NAME: str
    DISPLAY_NAME: str

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Enforce class-level attributes at definition time so errors surface
        # immediately, not at instantiation. Skip check for abstract subclasses.
        if not getattr(cls, "__abstractmethods__", None):
            for attr in ("SOURCE_NAME", "DISPLAY_NAME"):
                if not hasattr(cls, attr) or isinstance(
                    getattr(cls, attr), property
                ):
                    raise TypeError(
                        f"{cls.__name__} must define class attribute {attr!r}"
                    )

    @abstractmethod
    async def scrape(self, season: str, db: Any) -> int:
        """Fetch projections, resolve player names, upsert to player_projections.

        Args:
            season: e.g. "2025-26"
            db:     Supabase Client (service role)

        Returns:
            Number of player_projections rows upserted.

        Contract:
            - Must check robots.txt before any HTTP requests (use BaseScraper helpers).
            - Unmatched player names: log to scraper_logs, skip row, never raise.
            - Null stat vs zero stat: null means not projected; do not coerce to 0.
        """
