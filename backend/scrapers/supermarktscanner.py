"""
Scraper voor supermarktscanner.nl.
Één zoekopdracht levert prijzen van meerdere supermarkten tegelijk op.
De website vergelijkt al — wij extraheren die vergelijking.
"""
import json
import logging
import re
from typing import AsyncIterator, Optional

from bs4 import BeautifulSoup

from models.schemas import ProductScraped, PromoScraped
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://www.supermarktscanner.nl"

# Mapping van supermarktscanner-winkelnamen naar onze slugs
STORE_NAME_MAP = {
    "albert heijn": "albert_heijn",
    "ah": "albert_heijn",
    "jumbo": "jumbo",
    "lidl": "lidl",
    "plus": "plus",
    "dirk": "dirk",
    "aldi": "aldi",
    "coop": "coop",
    "hoogvliet": "hoogvliet",
    "jan linders": "jan_linders",
    "poiesz": "poiesz",
    "dekamarkt": "dekamarkt",
    "spar": "spar",
}


class SupermarktScannerScraper(BaseScraper):
    """
    Scraper voor supermarktscanner.nl.
    In tegenstelling tot andere scrapers geeft deze meteen ProductScraped
    objecten terug voor meerdere winkels per product.
    """
    store_slug = "supermarktscanner"
    store_name = "SupermarktScanner.nl"

    def __init__(self, request_delay_ms: int = 500):
        super().__init__(request_delay_ms)

    async def search(self, query: str, category_slug: str) -> AsyncIterator[ProductScraped]:
        """Zoek via Playwright en extraheer prijzen per winkel."""
        try:
            from playwright.async_api import async_playwright
            from config import settings
        except ImportError:
            logger.error("Playwright niet beschikbaar")
            return

        stealth_async = None
        try:
            from playwright_stealth import stealth_async
        except ImportError:
            try:
                from playwright_stealth import Stealth
                async def stealth_async(p):
                    await Stealth().apply_stealth_async(p)
            except ImportError:
                pass

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=settings.playwright_headless,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="nl-NL",
                viewport={"width": 1280, "height": 800},
            )
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = await context.new_page()
            if stealth_async:
                await stealth_async(page)

            try:
                # Probeer directe zoek-URL's
                search_urls = [
                    f"{BASE_URL}/zoeken?q={query}",
                    f"{BASE_URL}/search?q={query}",
                    f"{BASE_URL}/zoeken?query={query}",
                    f"{BASE_URL}/?s={query}",
                ]

                html = None
                for url in search_urls:
                    try:
                        resp = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                        if resp and resp.status == 200:
                            await page.wait_for_timeout(2000)
                            html = await page.content()
                            if "product" in html.lower() or "prijs" in html.lower():
                                logger.info("SupermarktScanner: werkende URL: %s", url)
                                break
                    except Exception as e:
                        logger.debug("SupermarktScanner URL %s mislukt: %s", url, e)

                # Als directe URL's niet werken: gebruik zoekbalk op homepage
                if not html or ("product" not in html.lower() and "prijs" not in html.lower()):
                    logger.info("SupermarktScanner: directe URL's mislukten, gebruik zoekbalk")
                    try:
                        await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=20000)
                        await page.wait_for_timeout(1500)

                        # Accepteer cookies
                        for sel in ["#onetrust-accept-btn-handler",
                                    "button:has-text('Accepteer')",
                                    "button:has-text('Akkoord')"]:
                            try:
                                btn = page.locator(sel).first
                                if await btn.is_visible(timeout=1500):
                                    await btn.click()
                                    await page.wait_for_timeout(500)
                                    break
                            except Exception:
                                pass

                        # Zoekbalk invullen
                        for sel in ["input[type='search']", "input[name='q']",
                                    "input[placeholder*='zoek']", "input[placeholder*='Zoek']",
                                    "#search", ".search-input"]:
                            try:
                                inp = page.locator(sel).first
                                if await inp.is_visible(timeout=2000):
                                    await inp.fill(query)
                                    await inp.press("Enter")
                                    await page.wait_for_timeout(3000)
                                    html = await page.content()
                                    logger.info("SupermarktScanner: gezocht via zoekbalk")
                                    break
                            except Exception:
                                pass
                    except Exception as e:
                        logger.error("SupermarktScanner homepage mislukt: %s", e)

                if not html:
                    logger.error("SupermarktScanner: geen pagina geladen voor '%s'", query)
                    await browser.close()
                    return

                # Extraheer prijzen per winkel
                products = self._extract_products(html, query, category_slug)
                logger.info(
                    "SupermarktScanner: %d prijs-vermeldingen gevonden voor '%s'",
                    len(products), query,
                )

                # Debug dump als er niets gevonden is
                if not products:
                    import tempfile, os
                    debug_path = os.path.join(
                        tempfile.gettempdir(),
                        f"sms_debug_{query[:20].replace(' ', '_')}.html"
                    )
                    with open(debug_path, "w", encoding="utf-8") as f:
                        f.write(html)
                    logger.warning(
                        "SupermarktScanner: 0 resultaten voor '%s' — URL: %s — debug: %s",
                        query, page.url, debug_path,
                    )

                for p in products:
                    yield p

            except Exception as e:
                logger.error("SupermarktScanner fout voor '%s': %s: %s", query, type(e).__name__, e)
            finally:
                await browser.close()

    def _extract_products(self, html: str, query: str, category_slug: str) -> list[ProductScraped]:
        soup = BeautifulSoup(html, "lxml")
        results = []

        # 1. JSON-LD
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
                    store_prices = self._extract_store_prices_from_jsonld(item)
                    for store_slug, price_cents, promo in store_prices:
                        results.append(ProductScraped(
                            store_slug=store_slug,
                            store_product_id=f"{item.get('sku', item.get('name', '')[:30])}_{store_slug}",
                            name=item.get("name", query),
                            brand=self._extract_brand(item),
                            category_slug=category_slug,
                            image_url=self._extract_image(item),
                            url=item.get("url"),
                            quantity_unit=item.get("description", "")[:100] or None,
                            price_cents=price_cents,
                            promotion=promo,
                        ))
            except (json.JSONDecodeError, AttributeError):
                continue

        if results:
            return results

        # 2. __NEXT_DATA__ of andere embedded JSON
        next_script = soup.find("script", id="__NEXT_DATA__")
        if next_script:
            try:
                data = json.loads(next_script.string or "")
                results.extend(self._extract_from_next_data(data, query, category_slug))
            except Exception:
                pass

        if results:
            return results

        # 3. HTML prijstabellen — supermarktscanner toont prijzen in een tabel/raster
        results.extend(self._extract_from_price_table(soup, query, category_slug))

        return results

    def _extract_store_prices_from_jsonld(
        self, item: dict
    ) -> list[tuple[str, int, Optional[PromoScraped]]]:
        """Extraheer (store_slug, price_cents, promo) uit JSON-LD offers."""
        results = []
        offers = item.get("offers", [])
        if isinstance(offers, dict):
            offers = [offers]

        for offer in offers:
            seller = offer.get("seller", {})
            seller_name = ""
            if isinstance(seller, dict):
                seller_name = seller.get("name", "").lower()
            elif isinstance(seller, str):
                seller_name = seller.lower()

            store_slug = self._map_store_name(seller_name)
            if not store_slug:
                continue

            try:
                price_cents = round(float(str(offer.get("price", 0)).replace(",", ".")) * 100)
            except (ValueError, TypeError):
                continue

            promo = None
            high = offer.get("highPrice")
            low = offer.get("lowPrice") or offer.get("price")
            if high and low:
                try:
                    if float(str(high)) > float(str(low)):
                        promo = PromoScraped(
                            promo_type="sale",
                            description=f"Was €{high}, nu €{low}",
                            promo_price_cents=round(float(str(low)) * 100),
                        )
                except (ValueError, TypeError):
                    pass

            results.append((store_slug, price_cents, promo))

        return results

    def _extract_from_next_data(self, data: dict, query: str, category_slug: str) -> list[ProductScraped]:
        results = []
        products_raw = self._find_in_obj(data, ["products", "items", "results", "hits"])
        for p in (products_raw or []):
            if not isinstance(p, dict):
                continue
            name = p.get("name") or p.get("title") or query
            # Zoek naar prijzen per winkel
            prices = p.get("prices") or p.get("storePrices") or p.get("offers") or []
            if isinstance(prices, dict):
                # Soms: {"albert_heijn": 1.99, "jumbo": 2.19}
                for store_key, price_val in prices.items():
                    store_slug = self._map_store_name(store_key)
                    if not store_slug:
                        continue
                    try:
                        price_cents = round(float(str(price_val).replace(",", ".")) * 100)
                    except (ValueError, TypeError):
                        continue
                    results.append(ProductScraped(
                        store_slug=store_slug,
                        store_product_id=f"{p.get('id', name[:30])}_{store_slug}",
                        name=str(name),
                        category_slug=category_slug,
                        price_cents=price_cents,
                    ))
            elif isinstance(prices, list):
                for offer in prices:
                    if not isinstance(offer, dict):
                        continue
                    store_name = (offer.get("store") or offer.get("supermarket") or
                                  offer.get("retailer") or "").lower()
                    store_slug = self._map_store_name(store_name)
                    if not store_slug:
                        continue
                    price_val = offer.get("price") or offer.get("amount") or 0
                    try:
                        price_cents = round(float(str(price_val).replace(",", ".")) * 100)
                    except (ValueError, TypeError):
                        continue
                    results.append(ProductScraped(
                        store_slug=store_slug,
                        store_product_id=f"{p.get('id', name[:30])}_{store_slug}",
                        name=str(name),
                        category_slug=category_slug,
                        price_cents=price_cents,
                    ))
        return results

    def _extract_from_price_table(self, soup, query: str, category_slug: str) -> list[ProductScraped]:
        """Extraheer uit HTML-prijstabellen zoals supermarktscanner die toont."""
        results = []

        # Zoek productrijen — elke rij heeft productinfo + prijs per winkel
        product_rows = (
            soup.find_all(class_=re.compile(r"product", re.I)) or
            soup.find_all("article") or
            soup.find_all("tr")
        )

        for row in product_rows:
            name_el = (row.find(class_=re.compile(r"name|title|product-name", re.I)) or
                       row.find("h2") or row.find("h3"))
            name = name_el.get_text(strip=True) if name_el else ""
            if not name:
                continue

            # Zoek prijzen per winkel in de rij
            price_cells = row.find_all(class_=re.compile(r"price|prijs", re.I))
            for cell in price_cells:
                # Winkel uit data-attribuut of omliggende element
                store_name = (cell.get("data-store") or cell.get("data-supermarket") or
                              cell.get("title") or "")
                if not store_name:
                    parent = cell.parent
                    if parent:
                        store_name = parent.get("data-store", "")

                store_slug = self._map_store_name(store_name.lower())
                if not store_slug:
                    continue

                price_str = cell.get_text(strip=True)
                price_cents = self._price_str_to_cents(price_str)
                if price_cents <= 0:
                    continue

                results.append(ProductScraped(
                    store_slug=store_slug,
                    store_product_id=f"{name[:30]}_{store_slug}",
                    name=name,
                    category_slug=category_slug,
                    price_cents=price_cents,
                ))

        return results

    def _find_in_obj(self, data, keys: list, depth: int = 0) -> Optional[list]:
        if depth > 10:
            return None
        if isinstance(data, dict):
            for key in keys:
                val = data.get(key)
                if isinstance(val, list) and val and isinstance(val[0], dict):
                    return val
            for v in data.values():
                r = self._find_in_obj(v, keys, depth + 1)
                if r:
                    return r
        elif isinstance(data, list):
            for item in data:
                r = self._find_in_obj(item, keys, depth + 1)
                if r:
                    return r
        return None

    def _map_store_name(self, name: str) -> Optional[str]:
        """Zet een winkelnaam om naar een slug."""
        name = name.lower().strip()
        for key, slug in STORE_NAME_MAP.items():
            if key in name or name in key:
                return slug
        return None

    def _extract_brand(self, item: dict) -> Optional[str]:
        b = item.get("brand")
        if isinstance(b, dict):
            return b.get("name")
        return str(b) if b else None

    def _extract_image(self, item: dict) -> Optional[str]:
        img = item.get("image")
        if isinstance(img, list):
            return img[0] if img else None
        return img

    async def health_check(self) -> bool:
        try:
            from playwright.async_api import async_playwright
            from config import settings
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=settings.playwright_headless)
                page = await browser.new_page()
                resp = await page.goto(BASE_URL, timeout=15000)
                await browser.close()
                return resp is not None and resp.status == 200
        except Exception as e:
            logger.warning("SupermarktScanner health check mislukt: %s", e)
            return False
