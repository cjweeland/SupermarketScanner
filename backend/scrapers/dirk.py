"""
Dirk scraper via Playwright + JSON-LD extractie.
"""
import json
import logging
from typing import AsyncIterator, Optional

from bs4 import BeautifulSoup

from models.schemas import ProductScraped, PromoScraped
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.dirk.nl/boodschappen/zoeken"
PRODUCT_BASE_URL = "https://www.dirk.nl"


class DirkScraper(BaseScraper):
    store_slug = "dirk"
    store_name = "Dirk"

    def __init__(self, request_delay_ms: int = 500):
        super().__init__(request_delay_ms)

    async def search(self, query: str, category_slug: str) -> AsyncIterator[ProductScraped]:
        try:
            from playwright.async_api import async_playwright
            from config import settings
        except ImportError:
            logger.error("Playwright niet geïnstalleerd voor Dirk scraper")
            return

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=settings.playwright_headless)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                locale="nl-NL",
            )
            page = await context.new_page()

            try:
                await page.goto(
                    f"{SEARCH_URL}?query={query}",
                    wait_until="networkidle",
                    timeout=30000,
                )
                await page.wait_for_timeout(2000)

                html = await page.content()
                products = self._extract_products(html, query, category_slug)
                for p in products:
                    yield p

            except Exception as e:
                logger.error("Dirk Playwright fout voor '%s': %s", query, e)
            finally:
                await browser.close()

    def _extract_products(self, html: str, query: str, category_slug: str) -> list[ProductScraped]:
        soup = BeautifulSoup(html, "lxml")
        results = []

        # JSON-LD structured data
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    for item in data:
                        if item.get("@type") == "Product":
                            p = self._parse_jsonld(item, category_slug)
                            if p:
                                results.append(p)
                elif data.get("@type") == "Product":
                    p = self._parse_jsonld(data, category_slug)
                    if p:
                        results.append(p)
                elif data.get("@type") == "ItemList":
                    for el in data.get("itemListElement", []):
                        item = el.get("item", el)
                        if item.get("@type") == "Product":
                            p = self._parse_jsonld(item, category_slug)
                            if p:
                                results.append(p)
            except (json.JSONDecodeError, AttributeError):
                continue

        if results:
            return results

        # Fallback: HTML product cards
        for card in soup.find_all(attrs={"data-product-id": True}):
            try:
                product_id = card.get("data-product-id", "")
                name_el = card.find(class_=lambda c: c and "name" in c.lower())
                name = name_el.get_text(strip=True) if name_el else ""
                if not name:
                    continue

                price_el = card.find(class_=lambda c: c and "price" in c.lower())
                price_str = price_el.get_text(strip=True) if price_el else "0"
                price_cents = self._price_str_to_cents(price_str)

                img_el = card.find("img")
                image_url = img_el.get("src") or img_el.get("data-src") if img_el else None

                link_el = card.find("a", href=True)
                url = None
                if link_el:
                    href = link_el["href"]
                    url = href if href.startswith("http") else PRODUCT_BASE_URL + href

                results.append(ProductScraped(
                    store_slug=self.store_slug,
                    store_product_id=product_id,
                    name=name,
                    category_slug=category_slug,
                    image_url=image_url,
                    url=url,
                    price_cents=price_cents,
                ))
            except Exception:
                continue

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
        brand_data = item.get("brand")
        if isinstance(brand_data, dict):
            brand = brand_data.get("name")
        elif brand_data:
            brand = str(brand_data)

        promo = None
        # Dirk heeft soms prijs-acties in de offer
        high_price = offer.get("highPrice")
        low_price = offer.get("lowPrice") or offer.get("price")
        if high_price and low_price and float(str(high_price)) > float(str(low_price)):
            promo = PromoScraped(
                promo_type="sale",
                description=f"Was €{high_price}, nu €{low_price}",
                promo_price_cents=round(float(str(low_price)) * 100),
            )

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
            promotion=promo,
        )

    async def health_check(self) -> bool:
        try:
            from playwright.async_api import async_playwright
            from config import settings
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=settings.playwright_headless)
                page = await browser.new_page()
                await page.goto("https://www.dirk.nl", timeout=15000)
                await browser.close()
            return True
        except Exception:
            return False
