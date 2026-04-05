"""
Plus scraper via Playwright (pure SPA).
Onderschept XHR requests om de onderliggende API te ontdekken.
"""
import json
import logging
from typing import AsyncIterator, Optional

from models.schemas import ProductScraped, PromoScraped
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.plus.nl/zoeken"
PRODUCT_BASE_URL = "https://www.plus.nl"


class PlusScraper(BaseScraper):
    store_slug = "plus"
    store_name = "Plus"

    def __init__(self, request_delay_ms: int = 500):
        super().__init__(request_delay_ms)

    async def search(self, query: str, category_slug: str) -> AsyncIterator[ProductScraped]:
        try:
            from playwright.async_api import async_playwright
            from config import settings
        except ImportError:
            logger.error("Playwright niet geïnstalleerd voor Plus scraper")
            return

        captured_products: list[dict] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=settings.playwright_headless)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                locale="nl-NL",
            )
            page = await context.new_page()

            # Onderschep API responses
            async def handle_response(response):
                url = response.url
                if "products" in url and "plus.nl" in url:
                    try:
                        body = await response.json()
                        if isinstance(body, dict) and body.get("products"):
                            captured_products.extend(body["products"])
                        elif isinstance(body, list):
                            captured_products.extend(body)
                    except Exception:
                        pass

            page.on("response", handle_response)

            try:
                await page.goto(
                    f"{SEARCH_URL}?search={query}",
                    wait_until="networkidle",
                    timeout=30000,
                )
                # Wacht extra voor lazy-loading
                await page.wait_for_timeout(2000)

                # Als network-interceptie niets opleverde, extraheer uit DOM
                if not captured_products:
                    html = await page.content()
                    captured_products.extend(self._extract_from_html(html))

            except Exception as e:
                logger.error("Plus Playwright fout voor '%s': %s", query, e)
            finally:
                await browser.close()

        for p in captured_products:
            try:
                parsed = self._parse_product(p, category_slug)
                if parsed:
                    yield parsed
            except Exception as e:
                logger.debug("Plus product parse fout: %s", e)
                continue

    def _extract_from_html(self, html: str) -> list[dict]:
        """Extracteer productdata uit HTML als network-interceptie niets opleverde."""
        from bs4 import BeautifulSoup
        import re

        products = []
        soup = BeautifulSoup(html, "lxml")

        # JSON-LD
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                items = data if isinstance(data, list) else data.get("itemListElement", [])
                for item in items:
                    p = item.get("item", item)
                    if p.get("@type") == "Product":
                        products.append({"_jsonld": p})
            except (json.JSONDecodeError, AttributeError):
                pass

        # data-product attributen
        for el in soup.find_all(attrs={"data-product": True}):
            try:
                products.append(json.loads(el["data-product"]))
            except (json.JSONDecodeError, TypeError):
                pass

        return products

    def _parse_product(self, p: dict, category_slug: str) -> Optional[ProductScraped]:
        # JSON-LD patroon
        if "_jsonld" in p:
            return self._parse_jsonld(p["_jsonld"], category_slug)

        name = p.get("name") or p.get("title", "")
        if not name:
            return None

        product_id = str(p.get("id") or p.get("sku") or p.get("code") or "")

        # Prijs
        price_cents = 0
        price = p.get("price") or p.get("currentPrice") or p.get("salesPrice")
        if price:
            if isinstance(price, dict):
                price = price.get("amount") or price.get("value") or 0
            try:
                price_cents = round(float(str(price).replace(",", ".")) * 100)
            except ValueError:
                pass

        # Promo
        promotion = None
        promo = p.get("promotionInfo") or p.get("promotion")
        if promo and isinstance(promo, dict):
            promo_desc = promo.get("description") or promo.get("text", "Aanbieding")
            promotion = PromoScraped(
                promo_type="promotion",
                description=promo_desc,
            )

        image_url = p.get("imageUrl") or p.get("image")
        if isinstance(image_url, dict):
            image_url = image_url.get("url")

        url = p.get("url") or p.get("pdpUrl")
        if url and not url.startswith("http"):
            url = PRODUCT_BASE_URL + url

        size = p.get("salesUnitSize") or p.get("contentQuantity") or ""

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
            promotion=promotion,
        )

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

        return ProductScraped(
            store_slug=self.store_slug,
            store_product_id=item.get("sku") or name[:50],
            name=name,
            brand=item.get("brand", {}).get("name") if isinstance(item.get("brand"), dict) else None,
            category_slug=category_slug,
            image_url=item.get("image"),
            url=url,
            quantity=None,
            quantity_unit=item.get("description", "")[:100] or None,
            price_cents=price_cents,
        )

    async def health_check(self) -> bool:
        try:
            from playwright.async_api import async_playwright
            from config import settings
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=settings.playwright_headless)
                page = await browser.new_page()
                await page.goto("https://www.plus.nl", timeout=15000)
                await browser.close()
            return True
        except Exception:
            return False
