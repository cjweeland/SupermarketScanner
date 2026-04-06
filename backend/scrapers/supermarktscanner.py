"""
Scraper voor supermarktscanner.nl.
Één zoekopdracht levert prijzen van meerdere supermarkten tegelijk op.
De website vergelijkt al — wij extraheren die vergelijking.
"""
import json
import logging
import re
import tempfile
import os
from typing import AsyncIterator, Optional
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from models.schemas import ProductScraped, PromoScraped
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://www.supermarktscanner.nl"
SEARCH_URL = f"{BASE_URL}/product.php?keyword={{keyword}}"

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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "nl-NL,nl;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
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
        url = SEARCH_URL.format(keyword=quote_plus(query))
        try:
            async with httpx.AsyncClient(
                headers=HEADERS,
                follow_redirects=True,
                timeout=20.0,
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text
        except Exception as e:
            logger.error("SupermarktScanner HTTP fout voor '%s': %s: %s", query, type(e).__name__, e)
            return

        products = self._extract_products(html, query, category_slug)
        logger.info(
            "SupermarktScanner: %d resultaten voor '%s'",
            len(products), query,
        )

        if not products:
            debug_path = os.path.join(
                tempfile.gettempdir(),
                f"sms_debug_{query[:20].replace(' ', '_')}.html",
            )
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(html)
            logger.warning(
                "SupermarktScanner: 0 resultaten voor '%s' — URL: %s — debug: %s",
                query, url, debug_path,
            )

        for p in products:
            yield p

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

        # 2. HTML prijstabellen / productrijen
        results.extend(self._extract_from_html(soup, query, category_slug))

        return results

    def _extract_from_html(self, soup, query: str, category_slug: str) -> list[ProductScraped]:
        """
        Verwerk de HTML van supermarktscanner.nl/product.php.
        We zoeken rijen/blokken met productnaam + prijzen per winkel.
        """
        results = []

        # Probeer tabel-rijen: <tr> met meerdere <td> waaronder winkelnamen/prijzen
        tables = soup.find_all("table")
        for table in tables:
            header_cells = table.find("tr")
            if not header_cells:
                continue
            headers = [th.get_text(strip=True).lower() for th in header_cells.find_all(["th", "td"])]

            for row in table.find_all("tr")[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue
                name = cells[0].get_text(strip=True)
                if not name or len(name) < 3:
                    continue

                # Kolom-headers bevatten winkelnamen
                for idx, header in enumerate(headers[1:], start=1):
                    store_slug = self._map_store_name(header)
                    if not store_slug or idx >= len(cells):
                        continue
                    price_cents = self._price_str_to_cents(cells[idx].get_text(strip=True))
                    if price_cents > 0:
                        results.append(ProductScraped(
                            store_slug=store_slug,
                            store_product_id=f"{name[:30]}_{store_slug}",
                            name=name,
                            category_slug=category_slug,
                            price_cents=price_cents,
                        ))

        if results:
            return results

        # Probeer kaart-/blok-structuur: elk product als artikel/div
        product_blocks = (
            soup.find_all(class_=re.compile(r"product[-_]?(row|item|card|result)", re.I)) or
            soup.find_all("article") or
            soup.find_all(class_=re.compile(r"row|item|card", re.I))
        )

        for block in product_blocks:
            name_el = (
                block.find(class_=re.compile(r"name|title|product[-_]?name", re.I)) or
                block.find("h2") or block.find("h3") or block.find("h4")
            )
            name = name_el.get_text(strip=True) if name_el else ""
            if not name:
                continue

            # Prijzen per winkel binnen het blok
            price_els = block.find_all(class_=re.compile(r"price|prijs", re.I))
            for el in price_els:
                store_name = (
                    el.get("data-store") or el.get("data-supermarket") or
                    el.get("title") or ""
                )
                if not store_name:
                    parent = el.parent
                    if parent:
                        store_name = (
                            parent.get("data-store", "") or
                            parent.get("title", "") or
                            parent.get_text(strip=True)[:30]
                        )

                store_slug = self._map_store_name(store_name.lower())
                if not store_slug:
                    continue

                price_cents = self._price_str_to_cents(el.get_text(strip=True))
                if price_cents > 0:
                    results.append(ProductScraped(
                        store_slug=store_slug,
                        store_product_id=f"{name[:30]}_{store_slug}",
                        name=name,
                        category_slug=category_slug,
                        price_cents=price_cents,
                    ))

        return results

    def _extract_store_prices_from_jsonld(
        self, item: dict
    ) -> list[tuple[str, int, Optional[PromoScraped]]]:
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

    def _map_store_name(self, name: str) -> Optional[str]:
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
            async with httpx.AsyncClient(headers=HEADERS, timeout=10.0) as client:
                resp = await client.get(BASE_URL)
                return resp.status_code == 200
        except Exception as e:
            logger.warning("SupermarktScanner health check mislukt: %s", e)
            return False
