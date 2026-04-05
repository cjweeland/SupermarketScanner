"""
Jumbo scraper via HTML + JSON-LD extractie van jumbo.com.
De mobiele API (mobileapi.jumbo.com) is niet langer beschikbaar.
Valt terug op Playwright als HTML-parsing onvoldoende resultaten geeft.
"""
import json
import logging
import re
from typing import AsyncIterator, Optional

import httpx
from bs4 import BeautifulSoup

from models.schemas import ProductScraped, PromoScraped
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.jumbo.com/zoeken/"
PRODUCT_BASE_URL = "https://www.jumbo.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.jumbo.com/",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
}


class JumboScraper(BaseScraper):
    store_slug = "jumbo"
    store_name = "Jumbo"

    def __init__(self, request_delay_ms: int = 400):
        super().__init__(request_delay_ms)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=HEADERS,
                timeout=20,
                follow_redirects=True,
            )
        return self._client

    async def search(self, query: str, category_slug: str) -> AsyncIterator[ProductScraped]:
        client = await self._get_client()
        await self._delay()

        try:
            resp = await client.get(
                SEARCH_URL,
                params={"searchTerms": query},
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(
                "Jumbo HTTP fout voor '%s': status %d — %s",
                query, e.response.status_code, e.response.text[:200],
            )
            async for p in self._playwright_fallback(query, category_slug):
                yield p
            return
        except httpx.RequestError as e:
            logger.error(
                "Jumbo verbindingsfout voor '%s': %s: %s",
                query, type(e).__name__, str(e) or "(geen details)",
            )
            async for p in self._playwright_fallback(query, category_slug):
                yield p
            return

        products = self._extract_products(resp.text, category_slug)

        if not products:
            logger.info("Jumbo: geen HTML-resultaten voor '%s', probeer Playwright", query)
            async for p in self._playwright_fallback(query, category_slug):
                yield p
            return

        for p in products:
            yield p

    def _extract_products(self, html: str, category_slug: str) -> list[ProductScraped]:
        soup = BeautifulSoup(html, "lxml")
        results = []

        # 1. JSON-LD structured data
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                items: list[dict] = []
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

        # 2. __NEXT_DATA__ embedded JSON (Next.js)
        next_data_script = soup.find("script", id="__NEXT_DATA__")
        if next_data_script:
            try:
                next_data = json.loads(next_data_script.string or "")
                products_raw = self._find_products_in_next(next_data)
                for p in products_raw:
                    parsed = self._parse_next_product(p, category_slug)
                    if parsed:
                        results.append(parsed)
            except (json.JSONDecodeError, AttributeError):
                pass

        if results:
            return results

        # 3. Inline data-product / data-* attributen
        for el in soup.find_all(attrs={"data-product": True}):
            try:
                p = json.loads(el["data-product"])
                parsed = self._parse_next_product(p, category_slug)
                if parsed:
                    results.append(parsed)
            except (json.JSONDecodeError, TypeError):
                pass

        return results

    def _find_products_in_next(self, data, depth: int = 0) -> list[dict]:
        """Recursief zoeken naar een 'products' lijst in __NEXT_DATA__."""
        if depth > 10:
            return []
        if isinstance(data, dict):
            for key in ("products", "items", "searchResults"):
                val = data.get(key)
                if isinstance(val, list) and val and isinstance(val[0], dict):
                    return val
            for v in data.values():
                result = self._find_products_in_next(v, depth + 1)
                if result:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = self._find_products_in_next(item, depth + 1)
                if result:
                    return result
        return []

    def _parse_jsonld(self, item: dict, category_slug: str) -> Optional[ProductScraped]:
        name = item.get("name", "")
        if not name:
            return None

        offer = item.get("offers", {})
        if isinstance(offer, list):
            offer = offer[0] if offer else {}

        try:
            price_cents = round(float(str(offer.get("price", 0)).replace(",", ".")) * 100)
        except (ValueError, TypeError):
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

        description = item.get("description", "")

        # Promo uit offers
        promotion = None
        high_price = offer.get("highPrice")
        low_price = offer.get("lowPrice") or offer.get("price")
        if high_price and low_price:
            try:
                if float(str(high_price)) > float(str(low_price)):
                    promotion = PromoScraped(
                        promo_type="sale",
                        description=f"Was €{high_price}, nu €{low_price}",
                        promo_price_cents=round(float(str(low_price)) * 100),
                    )
            except (ValueError, TypeError):
                pass

        return ProductScraped(
            store_slug=self.store_slug,
            store_product_id=item.get("sku") or item.get("productID") or name[:50],
            name=name,
            brand=brand,
            category_slug=category_slug,
            image_url=image_url,
            url=url,
            quantity=None,
            quantity_unit=description[:100] if description else None,
            price_cents=price_cents,
            promotion=promotion,
        )

    def _parse_next_product(self, p: dict, category_slug: str) -> Optional[ProductScraped]:
        name = p.get("title") or p.get("name", "")
        if not name:
            return None

        product_id = str(p.get("id") or p.get("sku") or "")

        # Prijs
        price_cents = 0
        prices = p.get("prices", {})
        if isinstance(prices, dict):
            price_obj = prices.get("price", {})
            if isinstance(price_obj, dict):
                try:
                    price_cents = round(float(str(price_obj.get("amount", 0))) * 100)
                except (ValueError, TypeError):
                    pass
            elif isinstance(price_obj, (int, float)):
                price_cents = round(float(price_obj) * 100)
        elif isinstance(prices, (int, float)):
            price_cents = round(float(prices) * 100)

        # Promo
        promotion = None
        promo_obj = prices.get("promotionalPrice") if isinstance(prices, dict) else None
        if promo_obj and isinstance(promo_obj, dict):
            try:
                promo_cents = round(float(str(promo_obj.get("amount", 0))) * 100)
                if promo_cents < price_cents:
                    promotion = PromoScraped(
                        promo_type="promotional_price",
                        description="Aanbiedingsprijs",
                        promo_price_cents=promo_cents,
                    )
            except (ValueError, TypeError):
                pass

        # Afbeelding
        image_url = None
        images = p.get("imageInfo", {}).get("primaryView", []) if isinstance(p.get("imageInfo"), dict) else []
        if images:
            image_url = images[0].get("url")

        # URL
        url = None
        slug = p.get("friendlyUrl") or p.get("urlKey") or ""
        if slug:
            url = f"{PRODUCT_BASE_URL}/producten/{slug}"

        quantity_str = str(p.get("quantity") or "")

        return ProductScraped(
            store_slug=self.store_slug,
            store_product_id=product_id or name[:50],
            name=name,
            brand=p.get("brand") or p.get("brandName"),
            category_slug=category_slug,
            image_url=image_url,
            url=url,
            quantity=None,
            quantity_unit=quantity_str if quantity_str else None,
            price_cents=price_cents,
            promotion=promotion,
        )

    async def _playwright_fallback(self, query: str, category_slug: str) -> AsyncIterator[ProductScraped]:
        """Playwright fallback als HTML-scraping mislukt."""
        try:
            from playwright.async_api import async_playwright
            from config import settings
        except ImportError:
            logger.error("Playwright niet beschikbaar als fallback voor Jumbo")
            return

        logger.info("Jumbo: Playwright fallback gestart voor '%s'", query)
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=settings.playwright_headless)
            context = await browser.new_context(
                user_agent=HEADERS["User-Agent"],
                locale="nl-NL",
            )
            page = await context.new_page()
            try:
                await page.goto(
                    f"{SEARCH_URL}?searchTerms={query}",
                    wait_until="networkidle",
                    timeout=30000,
                )
                await page.wait_for_timeout(2000)
                html = await page.content()
                for p in self._extract_products(html, category_slug):
                    yield p
            except Exception as e:
                logger.error("Jumbo Playwright fallback fout voor '%s': %s", query, e)
            finally:
                await browser.close()

    async def health_check(self) -> bool:
        try:
            client = await self._get_client()
            resp = await client.get(SEARCH_URL, params={"searchTerms": "melk"})
            return resp.status_code == 200
        except Exception as e:
            logger.warning("Jumbo health check mislukt: %s: %s", type(e).__name__, e)
            return False

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
