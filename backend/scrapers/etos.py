"""
Etos scraper via HTML + JSON-LD parsing.
Etos is onderdeel van Ahold Delhaize (zelfde groep als Albert Heijn).
"""
import json
import logging
from typing import AsyncIterator, Optional

import httpx
from bs4 import BeautifulSoup

from models.schemas import ProductScraped, PromoScraped
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.etos.nl/zoeken/"
PRODUCT_BASE_URL = "https://www.etos.nl"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "nl-NL,nl;q=0.9",
    "Referer": "https://www.etos.nl/",
}


class EtosScraper(BaseScraper):
    store_slug = "etos"
    store_name = "Etos"

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

        try:
            resp = await client.get(SEARCH_URL, params={"text": query})
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Etos search fout voor '%s': %s", query, e)
            return

        products = self._extract_products(resp.text, category_slug)
        for p in products:
            yield p

    def _extract_products(self, html: str, category_slug: str) -> list[ProductScraped]:
        soup = BeautifulSoup(html, "lxml")
        results = []

        # JSON-LD
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
                    p = self._parse_jsonld(item, category_slug)
                    if p:
                        results.append(p)
            except (json.JSONDecodeError, AttributeError):
                continue

        if results:
            return results

        # HTML product cards fallback
        selectors = [
            ("article", {"class": lambda c: c and "product" in " ".join(c).lower()}),
            ("div", {"class": lambda c: c and "product-tile" in " ".join(c).lower()}),
            ("li", {"class": lambda c: c and "product" in " ".join(c).lower()}),
        ]
        for tag, attrs in selectors:
            cards = soup.find_all(tag, attrs)
            if cards:
                for card in cards:
                    p = self._parse_html_card(card, category_slug)
                    if p:
                        results.append(p)
                break

        return results

    def _parse_jsonld(self, item: dict, category_slug: str) -> Optional[ProductScraped]:
        name = item.get("name", "")
        if not name:
            return None

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

        brand = None
        b = item.get("brand")
        if isinstance(b, dict):
            brand = b.get("name")
        elif b:
            brand = str(b)

        return ProductScraped(
            store_slug=self.store_slug,
            store_product_id=item.get("sku") or item.get("productID") or name[:50],
            name=name,
            brand=brand,
            category_slug=category_slug,
            image_url=image_url,
            url=url,
            quantity=None,
            quantity_unit=item.get("description", "")[:100] or None,
            price_cents=price_cents,
        )

    def _parse_html_card(self, card, category_slug: str) -> Optional[ProductScraped]:
        name_el = card.find(class_=lambda c: c and any(x in " ".join(c).lower() for x in ["name", "title"]))
        name = name_el.get_text(strip=True) if name_el else ""
        if not name:
            return None

        price_el = card.find(class_=lambda c: c and "price" in " ".join(c).lower())
        price_str = price_el.get_text(strip=True) if price_el else "0"
        price_cents = self._price_str_to_cents(price_str)

        img = card.find("img")
        image_url = (img.get("src") or img.get("data-src")) if img else None

        link = card.find("a", href=True)
        url = None
        if link:
            href = link["href"]
            url = href if href.startswith("http") else PRODUCT_BASE_URL + href

        return ProductScraped(
            store_slug=self.store_slug,
            store_product_id=card.get("data-product-id") or card.get("id") or name[:50],
            name=name,
            category_slug=category_slug,
            image_url=image_url,
            url=url,
            price_cents=price_cents,
        )

    async def health_check(self) -> bool:
        try:
            client = await self._get_client()
            resp = await client.get("https://www.etos.nl")
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
