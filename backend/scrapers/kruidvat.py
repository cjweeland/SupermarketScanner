"""
Kruidvat scraper.
Kruidvat blokkeert directe HTTP-requests (403 op alle endpoints).
Playwright is de primaire methode; JSON-LD extractie uit de gerenderde pagina.
"""
import json
import logging
from datetime import datetime
from typing import AsyncIterator, Optional

from bs4 import BeautifulSoup

from models.schemas import ProductScraped, PromoScraped
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

HOMEPAGE_URL = "https://www.kruidvat.nl"

# Zoekpagina-kandidaten — Playwright probeert ze op volgorde
SEARCH_CANDIDATES = [
    ("https://www.kruidvat.nl/zoeken", "text"),
    ("https://www.kruidvat.nl/zoeken", "q"),
    ("https://www.kruidvat.nl/search", "q"),
]


class KruidvatScraper(BaseScraper):
    store_slug = "kruidvat"
    store_name = "Kruidvat"

    def __init__(self, request_delay_ms: int = 500):
        super().__init__(request_delay_ms)

    async def search(self, query: str, category_slug: str) -> AsyncIterator[ProductScraped]:
        await self._delay()
        async for product in self._playwright_search(query, category_slug):
            yield product

    async def _playwright_search(self, query: str, category_slug: str) -> AsyncIterator[ProductScraped]:
        try:
            from playwright.async_api import async_playwright
            from config import settings
        except ImportError:
            logger.error("Playwright niet beschikbaar voor Kruidvat scraper")
            return

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=settings.playwright_headless)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="nl-NL",
                viewport={"width": 1280, "height": 800},
            )

            # Cookie-melding accepteren via homepage
            page = await context.new_page()
            try:
                await page.goto(HOMEPAGE_URL, wait_until="domcontentloaded", timeout=20000)
                # Accepteer cookie-banner als die er is
                for selector in [
                    "button[id*='accept']",
                    "button[class*='accept']",
                    "#onetrust-accept-btn-handler",
                    "button:has-text('Accepteer')",
                    "button:has-text('Akkoord')",
                ]:
                    try:
                        btn = page.locator(selector).first
                        if await btn.is_visible(timeout=2000):
                            await btn.click()
                            logger.debug("Kruidvat: cookie-banner geaccepteerd")
                            break
                    except Exception:
                        pass
            except Exception as e:
                logger.debug("Kruidvat: homepage laden mislukt (niet kritiek): %s", e)

            # Zoek de juiste zoek-URL
            search_url = None
            search_param = "text"
            for base_url, param in SEARCH_CANDIDATES:
                try:
                    resp = await page.goto(
                        f"{base_url}?{param}={query}",
                        wait_until="domcontentloaded",
                        timeout=20000,
                    )
                    if resp and resp.status == 200:
                        search_url = base_url
                        search_param = param
                        logger.info("Kruidvat: werkende URL: %s?%s=", base_url, param)
                        break
                    else:
                        logger.debug("Kruidvat: %s?%s= → %s", base_url, param, resp.status if resp else "geen respons")
                except Exception as e:
                    logger.debug("Kruidvat: URL-kandidaat mislukt %s: %s", base_url, e)

            if not search_url:
                logger.error("Kruidvat: geen werkende zoek-URL gevonden voor '%s'", query)
                await browser.close()
                return

            # Wacht op producten en extraheer
            try:
                await page.wait_for_timeout(2000)
                # Wacht op een productkaart als die zichtbaar wordt
                for selector in [
                    "[class*='product-tile']",
                    "[class*='product-card']",
                    "article",
                    "[data-test='product']",
                ]:
                    try:
                        await page.wait_for_selector(selector, timeout=5000)
                        break
                    except Exception:
                        pass

                html = await page.content()
                products = self._extract_from_html(html, category_slug)
                logger.info("Kruidvat: %d producten gevonden voor '%s'", len(products), query)
                for p in products:
                    yield p

            except Exception as e:
                logger.error("Kruidvat Playwright extractie fout voor '%s': %s", query, e)
            finally:
                await browser.close()

    def _extract_from_html(self, html: str, category_slug: str) -> list[ProductScraped]:
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

        # 2. HTML product cards
        for card in soup.find_all("article"):
            p = self._parse_html_card(card, category_slug)
            if p:
                results.append(p)

        if not results:
            # 3. data-product attributen
            for el in soup.find_all(attrs={"data-product": True}):
                try:
                    p_data = json.loads(el["data-product"])
                    name = p_data.get("name", "")
                    if not name:
                        continue
                    price = p_data.get("price") or p_data.get("currentPrice") or 0
                    try:
                        price_cents = round(float(str(price).replace(",", ".")) * 100)
                    except (ValueError, TypeError):
                        price_cents = 0
                    results.append(ProductScraped(
                        store_slug=self.store_slug,
                        store_product_id=str(p_data.get("id") or p_data.get("sku") or name[:50]),
                        name=name,
                        category_slug=category_slug,
                        price_cents=price_cents,
                    ))
                except (json.JSONDecodeError, TypeError):
                    pass

        return results

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
            url = HOMEPAGE_URL + url
        image_url = item.get("image")
        if isinstance(image_url, list):
            image_url = image_url[0] if image_url else None
        brand = None
        b = item.get("brand")
        if isinstance(b, dict):
            brand = b.get("name")
        elif b:
            brand = str(b)

        # Promotie uit offers
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
            quantity_unit=item.get("description", "")[:100] or None,
            price_cents=price_cents,
            promotion=promotion,
        )

    def _parse_html_card(self, card, category_slug: str) -> Optional[ProductScraped]:
        name_el = (
            card.find(attrs={"data-test": "product-name"})
            or card.find(class_=lambda c: c and "product-name" in " ".join(c).lower())
            or card.find("h3")
            or card.find("h2")
        )
        name = name_el.get_text(strip=True) if name_el else ""
        if not name:
            return None

        price_el = (
            card.find(attrs={"data-test": "product-price"})
            or card.find(class_=lambda c: c and "price" in " ".join(c).lower())
        )
        price_str = price_el.get_text(strip=True) if price_el else "0"
        price_cents = self._price_str_to_cents(price_str)

        img = card.find("img")
        image_url = (img.get("src") or img.get("data-src")) if img else None

        link = card.find("a", href=True)
        url = None
        if link:
            href = link["href"]
            url = href if href.startswith("http") else HOMEPAGE_URL + href

        return ProductScraped(
            store_slug=self.store_slug,
            store_product_id=card.get("data-product-code") or card.get("id") or name[:50],
            name=name,
            category_slug=category_slug,
            image_url=image_url,
            url=url,
            price_cents=price_cents,
        )

    async def health_check(self) -> bool:
        try:
            from playwright.async_api import async_playwright
            from config import settings
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=settings.playwright_headless)
                page = await browser.new_page()
                resp = await page.goto(HOMEPAGE_URL, timeout=15000)
                await browser.close()
                return resp is not None and resp.status == 200
        except Exception as e:
            logger.warning("Kruidvat health check mislukt: %s", e)
            return False
