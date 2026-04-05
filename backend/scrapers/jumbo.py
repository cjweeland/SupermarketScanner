"""
Jumbo scraper via de Jumbo Mobile API (geen authenticatie vereist).
"""
import logging
from typing import AsyncIterator, Optional

import httpx

from models.schemas import ProductScraped, PromoScraped
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

SEARCH_URL = "https://mobileapi.jumbo.com/v17/search"
PRODUCT_BASE_URL = "https://www.jumbo.com/producten/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Accept": "application/json",
}


class JumboScraper(BaseScraper):
    store_slug = "jumbo"
    store_name = "Jumbo"

    def __init__(self, request_delay_ms: int = 300):
        super().__init__(request_delay_ms)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(headers=HEADERS, timeout=15)
        return self._client

    async def search(self, query: str, category_slug: str) -> AsyncIterator[ProductScraped]:
        client = await self._get_client()
        offset = 0
        page_size = 30

        while True:
            await self._delay()
            try:
                resp = await client.get(
                    SEARCH_URL,
                    params={"q": query, "pageSize": page_size, "offset": offset},
                )
                resp.raise_for_status()
            except httpx.HTTPError as e:
                logger.error("Jumbo search fout voor '%s': %s", query, e)
                break

            data = resp.json()
            products_data = data.get("products", {}).get("data", [])
            if not products_data:
                break

            for p in products_data:
                try:
                    yield self._parse_product(p, category_slug)
                except Exception as e:
                    logger.debug("Jumbo product parse fout: %s", e)
                    continue

            total = data.get("products", {}).get("total", 0)
            offset += page_size
            if offset >= total or offset >= 90:  # max 3 pagina's
                break

    def _parse_product(self, p: dict, category_slug: str) -> ProductScraped:
        product_id = str(p.get("id", ""))
        title = p.get("title", "")
        name = title

        # Prijs
        prices = p.get("prices", {})
        price_obj = prices.get("price", {})
        price_cents = int(float(price_obj.get("amount", "0").replace(",", ".")))

        # Was-prijs
        promo_price_obj = prices.get("promotionalPrice")
        promotion = None
        if promo_price_obj:
            promo_cents = int(float(promo_price_obj.get("amount", "0").replace(",", ".")))
            if promo_cents < price_cents:
                promo_desc = p.get("promotion", {}).get("text", "Aanbiedingsprijs")
                promotion = PromoScraped(
                    promo_type="promotional_price",
                    description=promo_desc,
                    promo_price_cents=promo_cents,
                )

        # Unit prijs van Jumbo
        unit_price_obj = prices.get("unitPrice", {})
        unit_size = p.get("quantity") or p.get("quantityOptions", [{}])[0].get("defaultAmount", "") if p.get("quantityOptions") else ""

        # Afbeelding
        image_url = None
        images = p.get("imageInfo", {}).get("primaryView", [])
        if images:
            image_url = images[0].get("url")

        # URL
        url = None
        slug = p.get("friendlyUrl") or ""
        if slug:
            url = f"{PRODUCT_BASE_URL}{slug}"

        # Merkinfo
        brand = p.get("brand") or p.get("brandName")

        # Hoeveelheid
        quantity_str = str(p.get("quantity") or "")

        return ProductScraped(
            store_slug=self.store_slug,
            store_product_id=product_id,
            name=name,
            brand=brand,
            category_slug=category_slug,
            image_url=image_url,
            url=url,
            quantity=None,
            quantity_unit=quantity_str if quantity_str else None,
            price_cents=price_cents,
            promotion=promotion,
        )

    async def health_check(self) -> bool:
        try:
            client = await self._get_client()
            resp = await client.get(SEARCH_URL, params={"q": "melk", "pageSize": 1})
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
