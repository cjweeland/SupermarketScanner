"""
Kruidvat scraper.
Strategie:
1. Bezoek homepage om sessie-cookies op te halen
2. Probeer de REST API met die cookies
3. Fallback: scrape zoekpagina HTML met JSON-LD extractie
4. Laatste redmiddel: Playwright
"""
import json
import logging
from datetime import datetime
from typing import AsyncIterator, Optional

import httpx
from bs4 import BeautifulSoup

from models.schemas import ProductScraped, PromoScraped
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

HOMEPAGE_URL = "https://www.kruidvat.nl"
API_URL = "https://www.kruidvat.nl/api/2.0/products/search"
SEARCH_URL = "https://www.kruidvat.nl/zoeken"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-site": "same-origin",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
}


class KruidvatScraper(BaseScraper):
    store_slug = "kruidvat"
    store_name = "Kruidvat"

    def __init__(self, request_delay_ms: int = 500):
        super().__init__(request_delay_ms)
        self._client: Optional[httpx.AsyncClient] = None
        self._session_ready = False

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            # httpx bewaart cookies automatisch via cookiejar
            self._client = httpx.AsyncClient(
                headers={
                    **BROWSER_HEADERS,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
                timeout=20,
                follow_redirects=True,
            )
            self._session_ready = False
        return self._client

    async def _ensure_session(self) -> None:
        """Bezoek de homepage om sessie-cookies op te halen."""
        if self._session_ready:
            return
        client = await self._get_client()
        try:
            resp = await client.get(HOMEPAGE_URL)
            resp.raise_for_status()
            self._session_ready = True
            logger.debug("Kruidvat: sessie-cookies opgehaald (%d cookies)", len(client.cookies))
        except Exception as e:
            logger.warning("Kruidvat: homepage bezoek mislukt: %s: %s", type(e).__name__, e)

    async def search(self, query: str, category_slug: str) -> AsyncIterator[ProductScraped]:
        await self._ensure_session()
        await self._delay()

        # Stap 1: probeer de REST API
        products = await self._try_api(query, category_slug)

        # Stap 2: HTML-scraping van de zoekpagina
        if not products:
            logger.info("Kruidvat: API leverde niets op voor '%s', probeer HTML-scraping", query)
            products = await self._scrape_html(query, category_slug)

        # Stap 3: Playwright fallback
        if not products:
            logger.info("Kruidvat: HTML leverde niets op voor '%s', probeer Playwright", query)
            async for p in self._playwright_fallback(query, category_slug):
                yield p
            return

        for p in products:
            yield p

    async def _try_api(self, query: str, category_slug: str) -> list[ProductScraped]:
        client = await self._get_client()
        results = []
        page = 0

        while page <= 2:
            await self._delay()
            try:
                resp = await client.get(
                    API_URL,
                    params={
                        "query": query,
                        "pageSize": 24,
                        "currentPage": page,
                        "lang": "nl",
                        "curr": "EUR",
                    },
                    headers={
                        "Accept": "application/json, text/javascript, */*; q=0.01",
                        "X-Requested-With": "XMLHttpRequest",
                        "Referer": f"{SEARCH_URL}?q={query}",
                        "x-anonymous-consumerid": "kruidvat-web",
                    },
                )
            except httpx.RequestError as e:
                logger.error("Kruidvat API verbindingsfout: %s: %s", type(e).__name__, e)
                break

            if resp.status_code == 403:
                logger.warning(
                    "Kruidvat API geeft 403 voor '%s' (sessie-cookies niet geaccepteerd), "
                    "schakel over naar HTML-scraping",
                    query,
                )
                break
            if resp.status_code != 200:
                logger.warning("Kruidvat API status %d voor '%s'", resp.status_code, query)
                break

            try:
                data = resp.json()
            except Exception:
                break

            products_list = data.get("products", [])
            if not products_list:
                break

            for p in products_list:
                try:
                    parsed = self._parse_api_product(p, category_slug)
                    results.append(parsed)
                except Exception as e:
                    logger.debug("Kruidvat API parse fout: %s", e)

            pagination = data.get("pagination", {})
            if page + 1 >= pagination.get("totalPages", 1):
                break
            page += 1

        return results

    async def _scrape_html(self, query: str, category_slug: str) -> list[ProductScraped]:
        client = await self._get_client()
        try:
            resp = await client.get(
                SEARCH_URL,
                params={"q": query},
                headers={"Accept": "text/html,application/xhtml+xml,*/*;q=0.9"},
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error("Kruidvat HTML fout voor '%s': status %d", query, e.response.status_code)
            return []
        except httpx.RequestError as e:
            logger.error("Kruidvat HTML verbindingsfout: %s: %s", type(e).__name__, e)
            return []

        return self._extract_from_html(resp.text, category_slug)

    def _extract_from_html(self, html: str, category_slug: str) -> list[ProductScraped]:
        soup = BeautifulSoup(html, "lxml")
        results = []

        # JSON-LD structured data
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

        # Inline script met window.__STATE__ of window.__data__
        for script in soup.find_all("script"):
            text = script.string or ""
            if "window.__" in text and "products" in text.lower():
                import re
                # Zoek naar een JSON-object na window.__XXX__ =
                m = re.search(r"window\.__\w+__\s*=\s*(\{.+?\});?\s*(?:</script>|$)", text, re.DOTALL)
                if m:
                    try:
                        state = json.loads(m.group(1))
                        products = self._find_in_state(state, "products")
                        for p in (products or []):
                            parsed = self._parse_state_product(p, category_slug)
                            if parsed:
                                results.append(parsed)
                    except (json.JSONDecodeError, ValueError):
                        pass

        if results:
            return results

        # HTML product cards (class-based)
        for card in soup.find_all("article"):
            p = self._parse_html_card(card, category_slug)
            if p:
                results.append(p)

        return results

    def _find_in_state(self, data, key: str, depth: int = 0) -> Optional[list]:
        if depth > 8:
            return None
        if isinstance(data, dict):
            if key in data and isinstance(data[key], list):
                return data[key]
            for v in data.values():
                r = self._find_in_state(v, key, depth + 1)
                if r:
                    return r
        elif isinstance(data, list):
            for item in data:
                r = self._find_in_state(item, key, depth + 1)
                if r:
                    return r
        return None

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
        return ProductScraped(
            store_slug=self.store_slug,
            store_product_id=item.get("sku") or name[:50],
            name=name,
            brand=brand,
            category_slug=category_slug,
            image_url=image_url,
            url=url,
            quantity_unit=item.get("description", "")[:100] or None,
            price_cents=price_cents,
        )

    def _parse_state_product(self, p: dict, category_slug: str) -> Optional[ProductScraped]:
        name = p.get("name", "")
        if not name:
            return None
        price_str = (p.get("price", {}) or {}).get("formattedValue", "0")
        price_cents = self._price_str_to_cents(price_str)
        url_path = p.get("url", "")
        url = HOMEPAGE_URL + url_path if url_path else None
        return ProductScraped(
            store_slug=self.store_slug,
            store_product_id=p.get("code") or name[:50],
            name=name,
            brand=p.get("manufacturer"),
            category_slug=category_slug,
            url=url,
            price_cents=price_cents,
        )

    def _parse_html_card(self, card, category_slug: str) -> Optional[ProductScraped]:
        name_el = card.find(attrs={"data-test": "product-name"}) or \
                  card.find(class_=lambda c: c and "product-name" in " ".join(c).lower())
        name = name_el.get_text(strip=True) if name_el else ""
        if not name:
            return None

        price_el = card.find(attrs={"data-test": "product-price"}) or \
                   card.find(class_=lambda c: c and "price" in " ".join(c).lower())
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

    def _parse_api_product(self, p: dict, category_slug: str) -> ProductScraped:
        product_id = p.get("code", "")
        name = p.get("name", "")
        price_str = (p.get("price", {}) or {}).get("formattedValue", "0")
        price_cents = self._price_str_to_cents(price_str)

        promotion = None
        promos = p.get("potentialPromotions", [])
        if promos:
            promo = promos[0]
            promo_price_str = (promo.get("price", {}) or {}).get("formattedValue")
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
                description=promo.get("description", "Aanbieding"),
                promo_price_cents=promo_price_cents,
                valid_until=valid_until,
            )

        images = p.get("images", [])
        image_url = None
        for img in images:
            if img.get("format") == "product":
                img_url = img.get("url", "")
                image_url = img_url if img_url.startswith("http") else HOMEPAGE_URL + img_url
                break
        if not image_url and images:
            img_url = images[0].get("url", "")
            image_url = img_url if img_url.startswith("http") else HOMEPAGE_URL + img_url

        url_path = p.get("url", "")
        unit_str = f"{p.get('quantity', '')} {p.get('unit', '')}".strip()

        return ProductScraped(
            store_slug=self.store_slug,
            store_product_id=product_id,
            name=name,
            brand=p.get("manufacturer"),
            category_slug=category_slug,
            image_url=image_url,
            url=HOMEPAGE_URL + url_path if url_path else None,
            quantity_unit=unit_str if unit_str else None,
            price_cents=price_cents,
            promotion=promotion,
        )

    async def _playwright_fallback(self, query: str, category_slug: str) -> AsyncIterator[ProductScraped]:
        try:
            from playwright.async_api import async_playwright
            from config import settings
        except ImportError:
            logger.error("Playwright niet beschikbaar als fallback voor Kruidvat")
            return

        logger.info("Kruidvat: Playwright fallback voor '%s'", query)
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=settings.playwright_headless)
            context = await browser.new_context(
                user_agent=BROWSER_HEADERS["User-Agent"],
                locale="nl-NL",
            )
            page = await context.new_page()
            try:
                await page.goto(f"{SEARCH_URL}?q={query}", wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2000)
                html = await page.content()
                for p in self._extract_from_html(html, category_slug):
                    yield p
            except Exception as e:
                logger.error("Kruidvat Playwright fout voor '%s': %s", query, e)
            finally:
                await browser.close()

    async def health_check(self) -> bool:
        try:
            client = await self._get_client()
            resp = await client.get(HOMEPAGE_URL)
            return resp.status_code == 200
        except Exception as e:
            logger.warning("Kruidvat health check mislukt: %s", e)
            return False

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
