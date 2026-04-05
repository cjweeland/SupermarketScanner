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

        # Importeer stealth-plugin (verbergt Playwright-vingerafdruk voor Akamai)
        stealth_async = None
        try:
            from playwright_stealth import stealth_async  # versie 1.x
        except ImportError:
            try:
                from playwright_stealth import Stealth  # versie 2.x
                async def stealth_async(p):
                    await Stealth().apply_stealth_async(p)
            except ImportError:
                logger.warning("playwright-stealth niet beschikbaar (import mislukt) — ga door zonder stealth")

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=settings.playwright_headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                    "--window-size=1280,800",
                ],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="nl-NL",
                viewport={"width": 1280, "height": 800},
                extra_http_headers={
                    "Accept-Language": "nl-NL,nl;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            )
            # Verberg navigator.webdriver vlag
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = await context.new_page()
            # Pas stealth toe als de package beschikbaar is
            if stealth_async:
                await stealth_async(page)

            try:
                # Stap 1: open homepage
                logger.debug("Kruidvat: homepage laden...")
                await page.goto(HOMEPAGE_URL, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(1500)

                # Stap 2: accepteer cookie-banner
                for selector in [
                    "#onetrust-accept-btn-handler",
                    "button[id*='accept']",
                    "button:has-text('Accepteer alles')",
                    "button:has-text('Accepteer')",
                    "button:has-text('Akkoord')",
                    "button:has-text('Alle cookies')",
                ]:
                    try:
                        btn = page.locator(selector).first
                        if await btn.is_visible(timeout=1500):
                            await btn.click()
                            await page.wait_for_timeout(800)
                            logger.debug("Kruidvat: cookie-banner geaccepteerd via '%s'", selector)
                            break
                    except Exception:
                        pass

                # Stap 3: gebruik de zoekbalk op de pagina
                search_input_selectors = [
                    "input[type='search']",
                    "input[name='q']",
                    "input[name='text']",
                    "input[placeholder*='zoek']",
                    "input[placeholder*='Zoek']",
                    "input[class*='search']",
                    "#search",
                    "[data-test='search-input']",
                ]
                typed = False
                for sel in search_input_selectors:
                    try:
                        inp = page.locator(sel).first
                        if await inp.is_visible(timeout=2000):
                            await inp.click()
                            await inp.fill(query)
                            await inp.press("Enter")
                            typed = True
                            logger.debug("Kruidvat: zoekopdracht '%s' ingevoerd via '%s'", query, sel)
                            break
                    except Exception:
                        pass

                if not typed:
                    # Directe URL als fallback
                    logger.debug("Kruidvat: zoekbalk niet gevonden, probeer directe URL")
                    for base_url, param in SEARCH_CANDIDATES:
                        try:
                            await page.goto(
                                f"{base_url}?{param}={query}",
                                wait_until="domcontentloaded",
                                timeout=20000,
                            )
                            await page.wait_for_timeout(2000)
                            html = await page.content()
                            if "product" in html.lower():
                                break
                        except Exception:
                            pass

                # Stap 4: wacht op laadresultaten
                await page.wait_for_timeout(3000)
                for selector in [
                    "[class*='product-tile']",
                    "[class*='product-card']",
                    "[class*='ProductTile']",
                    "article",
                    "[data-test*='product']",
                ]:
                    try:
                        await page.wait_for_selector(selector, timeout=4000)
                        logger.debug("Kruidvat: productkaarten gevonden via '%s'", selector)
                        break
                    except Exception:
                        pass

                # Stap 5: extraheer producten
                html = await page.content()
                products = self._extract_from_html(html, category_slug)

                if products:
                    logger.info("Kruidvat: %d producten gevonden voor '%s'", len(products), query)
                else:
                    # Sla debug-HTML op zodat we de structuur kunnen inspecteren
                    import tempfile, os
                    debug_path = os.path.join(tempfile.gettempdir(), f"kruidvat_debug_{query[:20].replace(' ','_')}.html")
                    with open(debug_path, "w", encoding="utf-8") as f:
                        f.write(html)
                    logger.warning(
                        "Kruidvat: 0 producten voor '%s' — URL: %s — debug HTML opgeslagen in: %s",
                        query, page.url, debug_path,
                    )

                for p in products:
                    yield p

            except Exception as e:
                logger.error("Kruidvat Playwright fout voor '%s': %s: %s", query, type(e).__name__, e)
            finally:
                await browser.close()

    def _extract_from_html(self, html: str, category_slug: str) -> list[ProductScraped]:
        soup = BeautifulSoup(html, "lxml")
        results = []

        # 0. __NEXT_DATA__ (Next.js embedded state — meest betrouwbaar)
        next_script = soup.find("script", id="__NEXT_DATA__")
        if next_script:
            try:
                next_data = json.loads(next_script.string or "")
                products_raw = self._find_products_in_obj(next_data)
                for p in products_raw:
                    parsed = self._parse_next_product(p, category_slug)
                    if parsed:
                        results.append(parsed)
                if results:
                    return results
            except (json.JSONDecodeError, AttributeError):
                pass

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

    def _find_products_in_obj(self, data, depth: int = 0) -> list[dict]:
        """Recursief zoeken naar een lijst van producten in een JSON-object."""
        if depth > 12:
            return []
        if isinstance(data, dict):
            # Zoek naar lijsten met product-achtige objecten
            for key in ("products", "items", "results", "searchResults", "productList", "hits"):
                val = data.get(key)
                if isinstance(val, list) and val:
                    first = val[0]
                    if isinstance(first, dict) and any(
                        k in first for k in ("name", "title", "productName", "ean", "sku", "price")
                    ):
                        return val
            for v in data.values():
                r = self._find_products_in_obj(v, depth + 1)
                if r:
                    return r
        elif isinstance(data, list):
            for item in data:
                r = self._find_products_in_obj(item, depth + 1)
                if r:
                    return r
        return []

    def _parse_next_product(self, p: dict, category_slug: str) -> Optional[ProductScraped]:
        name = (
            p.get("name") or p.get("title") or p.get("productName") or
            p.get("displayName") or ""
        )
        if not name:
            return None

        product_id = str(
            p.get("id") or p.get("sku") or p.get("code") or
            p.get("ean") or p.get("productId") or name[:50]
        )

        # Prijs — diverse mogelijke structuren
        price_cents = 0
        for price_key in ("price", "currentPrice", "salesPrice", "priceData"):
            price_val = p.get(price_key)
            if price_val is None:
                continue
            if isinstance(price_val, dict):
                raw = (
                    price_val.get("value") or price_val.get("amount") or
                    price_val.get("formattedValue") or price_val.get("price") or 0
                )
            else:
                raw = price_val
            try:
                price_cents = round(float(str(raw).replace(",", ".").replace("€", "").strip()) * 100)
                if price_cents > 0:
                    break
            except (ValueError, TypeError):
                pass

        # Promo
        promotion = None
        for promo_key in ("promotions", "promotion", "badge", "badges"):
            promo_val = p.get(promo_key)
            if not promo_val:
                continue
            if isinstance(promo_val, list) and promo_val:
                promo_val = promo_val[0]
            if isinstance(promo_val, dict):
                desc = promo_val.get("description") or promo_val.get("text") or promo_val.get("label")
                if desc:
                    promotion = PromoScraped(promo_type="promotion", description=str(desc))
                    break
            elif isinstance(promo_val, str) and promo_val:
                promotion = PromoScraped(promo_type="promotion", description=promo_val)
                break

        # Afbeelding
        image_url = p.get("imageUrl") or p.get("image") or p.get("thumbnail")
        if isinstance(image_url, dict):
            image_url = image_url.get("url") or image_url.get("src")
        if image_url and not str(image_url).startswith("http"):
            image_url = HOMEPAGE_URL + str(image_url)

        # URL
        url = p.get("url") or p.get("pdpUrl") or p.get("slug")
        if url and not str(url).startswith("http"):
            url = HOMEPAGE_URL + str(url)

        # Hoeveelheid
        size = p.get("unitSize") or p.get("packageSize") or p.get("contentQuantity") or p.get("size") or ""

        return ProductScraped(
            store_slug=self.store_slug,
            store_product_id=product_id,
            name=str(name),
            brand=p.get("brand") or p.get("brandName"),
            category_slug=category_slug,
            image_url=str(image_url) if image_url else None,
            url=str(url) if url else None,
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
