"""
Kruidvat scraper via de Kruidvat REST API.
"""
import logging
from typing import AsyncIterator, Optional
from datetime import datetime

import httpx

from models.schemas import ProductScraped, PromoScraped
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.kruidvat.nl/api/2.0/products/search"
PRODUCT_BASE_URL = "https://www.kruidvat.nl"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.kruidvat.nl/",
    "x-anonymous-consumerid": "kruidvat-web",
}


class KruidvatScraper(BaseScraper):
    store_slug = "kruidvat"
    store_name = "Kruidvat"

    def __init__(self, request_delay_ms: int = 400):
        super().__init__(request_delay_ms)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True)
        return self._client

    async def search(self, query: str, category_slug: str) -> AsyncIterator[ProductScraped]:
        client = await self._get_client()
        page = 0

        while True:
            await self._delay()
            try:
                resp = await client.get(
                    SEARCH_URL,
                    params={
                        "query": query,
                        "pageSize": 24,
                        "currentPage": page,
                        "lang": "nl",
                        "curr": "EUR",
                    },
                )
                resp.raise_for_status()
            except httpx.HTTPError as e:
                logger.error("Kruidvat search fout voor '%s': %s", query, e)
                break

            data = resp.json()
            products_list = data.get("products", [])
            if not products_list:
                break

            for p in products_list:
                try:
                    yield self._parse_product(p, category_slug)
                except Exception as e:
                    logger.debug("Kruidvat product parse fout: %s", e)
                    continue

            # Paginering
            pagination = data.get("pagination", {})
            total_pages = pagination.get("totalPages", 1)
            if page + 1 >= total_pages or page >= 2:
                break
            page += 1

    def _parse_product(self, p: dict, category_slug: str) -> ProductScraped:
        product_id = p.get("code", "")
        name = p.get("name", "")

        # Prijs
        price_data = p.get("price", {})
        price_str = price_data.get("formattedValue", "0")
        price_cents = self._price_str_to_cents(price_str)

        # Was-prijs / aanbiedingen
        promotion = None
        promos = p.get("potentialPromotions", [])
        if promos:
            promo = promos[0]
            promo_desc = promo.get("description", "Aanbieding")
            promo_price_data = promo.get("price", {})
            promo_price_str = promo_price_data.get("formattedValue") if promo_price_data else None
            promo_price_cents = self._price_str_to_cents(promo_price_str) if promo_price_str else None
            valid_until = None
            end_date = promo.get("endDate")
            if end_date:
                try:
                    valid_until = datetime.fromisoformat(end_date)
                except ValueError:
                    pass
            promotion = PromoScraped(
                promo_type="promotion",
                description=promo_desc,
                promo_price_cents=promo_price_cents,
                valid_until=valid_until,
            )

        # Volume prijs (Kruidvat geeft dit soms mee)
        volume_prices = p.get("volumePrices", [])

        # Afbeelding
        image_url = None
        images = p.get("images", [])
        for img in images:
            if img.get("format") == "product":
                img_url = img.get("url", "")
                image_url = img_url if img_url.startswith("http") else PRODUCT_BASE_URL + img_url
                break
        if not image_url and images:
            img_url = images[0].get("url", "")
            image_url = img_url if img_url.startswith("http") else PRODUCT_BASE_URL + img_url

        # URL
        url_path = p.get("url", "")
        url = PRODUCT_BASE_URL + url_path if url_path else None

        # Merk
        brand = None
        manufacturer = p.get("manufacturer")
        if manufacturer:
            brand = manufacturer

        # Eenheid
        unit_of_measure = p.get("unit") or p.get("packagingUnit") or ""
        quantity_str = ""
        if p.get("quantity"):
            quantity_str = f"{p['quantity']} {unit_of_measure}".strip()

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
            resp = await client.get(SEARCH_URL, params={"query": "shampoo", "pageSize": 1, "lang": "nl"})
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
