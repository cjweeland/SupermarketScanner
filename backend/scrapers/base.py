"""
Abstract base class voor alle winkelscrapers.
"""
import asyncio
import logging
import traceback
from abc import ABC, abstractmethod
from typing import AsyncIterator

from models.schemas import ProductScraped

logger = logging.getLogger(__name__)


def log_scrape_error(store: str, query: str, exc: Exception) -> None:
    """Log een scrape-fout met volledig type en bericht."""
    msg = str(exc) or "(geen foutbericht)"
    logger.error(
        "%s search fout voor '%s': %s: %s",
        store, query, type(exc).__name__, msg,
    )
    logger.debug("Volledige stacktrace:\n%s", traceback.format_exc())


class BaseScraper(ABC):
    store_slug: str
    store_name: str

    def __init__(self, request_delay_ms: int = 300):
        self.request_delay_ms = request_delay_ms

    @abstractmethod
    async def search(self, query: str, category_slug: str) -> AsyncIterator[ProductScraped]:
        """Zoek producten op en yield ProductScraped objecten."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Eenvoudige test of de winkel bereikbaar is. Geeft True terug bij succes."""
        ...

    async def _delay(self) -> None:
        if self.request_delay_ms > 0:
            await asyncio.sleep(self.request_delay_ms / 1000)

    @staticmethod
    def _price_str_to_cents(price_str: str) -> int:
        """Zet een prijsstring om naar centen. Bijv. '€ 1,99' → 199."""
        cleaned = (
            price_str
            .replace("€", "")
            .replace("\u20ac", "")
            .strip()
        )
        if "," in cleaned and "." in cleaned:
            # Formaat: 1.299,99 (duizendtal punt, decimaal komma)
            cleaned = cleaned.replace(".", "").replace(",", ".")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        try:
            return round(float(cleaned) * 100)
        except ValueError:
            return 0

    @staticmethod
    def _float_to_cents(value: float) -> int:
        return round(value * 100)
