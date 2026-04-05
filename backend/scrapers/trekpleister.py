"""
Trekpleister scraper via HTML + JSON-LD parsing.
Trekpleister is onderdeel van A.S. Watson (zelfde groep als Kruidvat).
"""
import json
import logging
from typing import AsyncIterator, Optional

import httpx
from bs4 import BeautifulSoup

from models.schemas import ProductScraped
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.trekpleister.nl/zoeken"
PRODUCT_BASE_URL = "https://www.trekpleister.nl"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "nl-NL,nl;q=0.9",
    "Referer": "https://www.trekpleister.nl/",
}


class TrekpleisterScraper(BaseScraper):
    store_slug = "trekpleister"
    store_name = "Trekpleister"

    def __init__(self, request_delay_ms: int = 400):
        super().__init__(request_delay_ms)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True)
        return self._client

    async def search(self, query: str, category_slug: str) -> AsyncIterator[ProductScraped]:
        client = await self._get_client()
        await self._delay()

        # Probeer eerst de Kruidvat API-achtige endpoint (gedeelde backend)
        async for p in self._try_api_search(query, category_slug):
            yield p
            return

        try:
            resp = await client.get(SEARCH_URL, params={"q": query})
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Trekpleister search fout voor '%s': %s", query, e)
            return

        products = self._extract_products(resp.text, category_slug)
        for p in products:
            yield p

    async def _try_api_search(self, query: str, category_slug: str) -> AsyncIterator[ProductScraped]:
        """Probeer de AS Watson/Kruidvat-achtige REST API (gedeelde infrastructuur)."""
        client = await self._get_client()
        api_url = "https://www.trekpleister.nl/api/2.0/products/search"
        try:
            resp = await client.get(
                api_url,
                params={"query": query, "pageSize": 24, "currentPage": 0, "lang": "nl", "curr": "EUR"},
            )
            if resp.status_code != 200:
                return
            data = resp.json()
            products_list = data.get("products", [])
            for p in products_list:
                parsed = self._parse_api_product(p, category_slug)
                if parsed:
                    yield parsed
        except Exception as e:
            logger.debug("Trekpleister API poging mislukt: %s", e)

    def _parse_api_product(self, p: dict, category_slug: str) -> Optional[ProductScraped]:
        name = p.get("name", "")
        if not name:
            return None
        price_str = (p.get("price", {}) or {}).get("formattedValue", "0")
        price_cents = self._price_str_to_cents(price_str)
        url_path = p.get("url", "")
        url = PRODUCT_BASE_URL + url_path if url_path else None
        images = p.get("images", [])
        image_url = None
        for img in images:
            if img.get("format") == "product":
                img_url = img.get("url", "")
                image_url = img_url if img_url.startswith("http") else PRODUCT_BASE_URL + img_url
                break
        return ProductScraped(
            store_slug=self.store_slug,
            store_product_id=p.get("code", name[:50]),
            name=name,
            category_slug=category_slug,
            image_url=image_url,
            url=url,
            price_cents=price_cents,
        )

    def _extract_products(self, html: str, category_slug: str) -> list[ProductScraped]:
        soup = BeautifulSoup(html, "lxml")
        results = []

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                items = []
                if isinstance(data, list):
                    items = [i for i in data if i.get("@type") == "Product"]
                elif data.get("@type") == "Product":
                    items = [data]
                elif data.get("@type") == "ItemList":
                    for el in data.get("itemListElement", []):
                        it = el.get("item", el)
                        if it.get("@type") == "Product":
                            items.append(it)
                for item in items:
                    name = item.get("name", "")
                    if not name:
                        continue
                    offer = item.get("offers", {})
                    if isinstance(offer, list):
                        offer = offer[0] if offer else {}
                    try:
                        price_cents = round(float(str(offer.get("price", 0))) * 100)
                    except ValueError:
                        price_cents = 0
                    url = item.get("url")
                    if url and not url.startswith("http"):
                        url = PRODUCT_BASE_URL + url
                    image_url = item.get("image")
                    if isinstance(image_url, list):
                        image_url = image_url[0] if image_url else None
                    results.append(ProductScraped(
                        store_slug=self.store_slug,
                        store_product_id=item.get("sku") or name[:50],
                        name=name,
                        category_slug=category_slug,
                        image_url=image_url,
                        url=url,
                        quantity_unit=item.get("description", "")[:100] or None,
                        price_cents=price_cents,
                    ))
            except (json.JSONDecodeError, AttributeError):
                continue

        return results

    async def health_check(self) -> bool:
        try:
            client = await self._get_client()
            resp = await client.get("https://www.trekpleister.nl")
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
