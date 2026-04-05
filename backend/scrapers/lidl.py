"""
Lidl scraper: pakt producten uit de __NUXT__ JSON data in HTML-pagina's.
Valt terug op Playwright als het parse mislukt.
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

SEARCH_URL = "https://www.lidl.nl/q/zoeken?q={query}"
PRODUCT_BASE_URL = "https://www.lidl.nl"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "nl-NL,nl;q=0.9",
    "Referer": "https://www.lidl.nl/",
}


class LidlScraper(BaseScraper):
    store_slug = "lidl"
    store_name = "Lidl"

    def __init__(self, request_delay_ms: int = 500):
        super().__init__(request_delay_ms)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True)
        return self._client

    async def search(self, query: str, category_slug: str) -> AsyncIterator[ProductScraped]:
        client = await self._get_client()
        await self._delay()

        url = SEARCH_URL.format(query=query)
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Lidl search fout voor '%s': %s", query, e)
            # Probeer Playwright fallback
            async for product in self._playwright_search(query, category_slug):
                yield product
            return

        html = resp.text
        products = self._extract_from_nuxt(html, query, category_slug)

        if products:
            for p in products:
                yield p
        else:
            logger.warning("Lidl: geen __NUXT__ data voor '%s', gebruik Playwright fallback", query)
            async for product in self._playwright_search(query, category_slug):
                yield product

    def _extract_from_nuxt(self, html: str, query: str, category_slug: str) -> list[ProductScraped]:
        """Extraheer productdata uit de __NUXT__ embedded JSON."""
        soup = BeautifulSoup(html, "lxml")
        results = []

        # Probeer JSON-LD structured data eerst
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    for item in data:
                        if item.get("@type") == "Product":
                            p = self._parse_jsonld_product(item, category_slug)
                            if p:
                                results.append(p)
                elif data.get("@type") == "ItemList":
                    for item in data.get("itemListElement", []):
                        product_item = item.get("item", item)
                        if product_item.get("@type") == "Product":
                            p = self._parse_jsonld_product(product_item, category_slug)
                            if p:
                                results.append(p)
            except (json.JSONDecodeError, AttributeError):
                continue

        if results:
            return results

        # Probeer __NUXT__ patroon
        nuxt_match = re.search(r"window\.__NUXT__\s*=\s*(\{.+?\});?\s*</script>", html, re.DOTALL)
        if not nuxt_match:
            return []

        try:
            nuxt_str = nuxt_match.group(1)
            # Basisopschoning: vervang undefined/NaN/Infinity
            nuxt_str = re.sub(r"\bundefined\b", "null", nuxt_str)
            nuxt_str = re.sub(r"\bNaN\b", "null", nuxt_str)
            nuxt_data = json.loads(nuxt_str)
        except json.JSONDecodeError:
            return []

        # Navigeer door de NUXT state om producten te vinden
        products_raw = self._find_in_nuxt(nuxt_data, "products") or []
        for p in products_raw:
            try:
                parsed = self._parse_nuxt_product(p, category_slug)
                if parsed:
                    results.append(parsed)
            except Exception:
                continue

        return results

    def _find_in_nuxt(self, data, key: str, depth: int = 0):
        """Recursief zoeken naar een sleutel in NUXT data."""
        if depth > 8:
            return None
        if isinstance(data, dict):
            if key in data and isinstance(data[key], list):
                return data[key]
            for v in data.values():
                result = self._find_in_nuxt(v, key, depth + 1)
                if result:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = self._find_in_nuxt(item, key, depth + 1)
                if result:
                    return result
        return None

    def _parse_jsonld_product(self, item: dict, category_slug: str) -> Optional[ProductScraped]:
        name = item.get("name", "")
        if not name:
            return None

        product_id = item.get("sku") or item.get("productID") or name[:50]

        # Prijs uit JSON-LD offer
        offer = item.get("offers", {})
        if isinstance(offer, list):
            offer = offer[0] if offer else {}
        price_str = str(offer.get("price", "0"))
        try:
            price_cents = round(float(price_str) * 100)
        except ValueError:
            price_cents = 0

        image_url = item.get("image")
        if isinstance(image_url, list):
            image_url = image_url[0] if image_url else None
        url = item.get("url")
        if url and not url.startswith("http"):
            url = PRODUCT_BASE_URL + url

        brand_data = item.get("brand", {})
        brand = brand_data.get("name") if isinstance(brand_data, dict) else str(brand_data)

        description = item.get("description", "")

        return ProductScraped(
            store_slug=self.store_slug,
            store_product_id=str(product_id),
            name=name,
            brand=brand,
            category_slug=category_slug,
            image_url=image_url,
            url=url,
            quantity=None,
            quantity_unit=description[:100] if description else None,
            price_cents=price_cents,
        )

    def _parse_nuxt_product(self, p: dict, category_slug: str) -> Optional[ProductScraped]:
        name = p.get("name") or p.get("fullName", "")
        if not name:
            return None
        product_id = str(p.get("id") or p.get("sku") or name[:30])
        price = p.get("price", {})
        if isinstance(price, dict):
            price_val = price.get("price") or price.get("regularPrice") or 0
        else:
            price_val = price or 0
        price_cents = round(float(price_val) * 100) if price_val else 0

        promo = None
        if p.get("isPromotion") or p.get("discount"):
            promo_desc = p.get("promotionText") or "Lidl+ aanbieding"
            promo_price = p.get("promotionPrice")
            promo = PromoScraped(
                promo_type="lidl_plus",
                description=promo_desc,
                promo_price_cents=round(float(promo_price) * 100) if promo_price else None,
                requires_membership=True,
            )

        image_url = p.get("imageUrl") or (p.get("images") or [{}])[0].get("url") if p.get("images") else None
        url = p.get("canonicalUrl") or p.get("url")
        if url and not url.startswith("http"):
            url = PRODUCT_BASE_URL + url

        size = p.get("packageSize") or p.get("contentQuantity") or ""

        return ProductScraped(
            store_slug=self.store_slug,
            store_product_id=product_id,
            name=name,
            brand=p.get("brand"),
            category_slug=category_slug,
            image_url=image_url,
            url=url,
            quantity=None,
            quantity_unit=str(size) if size else None,
            price_cents=price_cents,
            promotion=promo,
        )

    async def _playwright_search(self, query: str, category_slug: str) -> AsyncIterator[ProductScraped]:
        """Playwright fallback voor Lidl als HTML-parsing mislukt."""
        try:
            from playwright.async_api import async_playwright
            from config import settings
        except ImportError:
            logger.error("Playwright niet geïnstalleerd")
            return

        url = SEARCH_URL.format(query=query)
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=settings.playwright_headless)
            page = await browser.new_page()
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                # Haal JSON-LD op na JS rendering
                html = await page.content()
                products = self._extract_from_nuxt(html, query, category_slug)
                for p in products:
                    yield p
            except Exception as e:
                logger.error("Lidl Playwright fout: %s", e)
            finally:
                await browser.close()

    async def health_check(self) -> bool:
        try:
            client = await self._get_client()
            resp = await client.get("https://www.lidl.nl")
            return resp.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
