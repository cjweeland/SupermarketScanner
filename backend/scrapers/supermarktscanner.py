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
        Structuur:
          div.product-entry[data-name="..."]
            div.cbp-pgitem  (één per winkel)
              span.shoplogo > img[src="/img/shops_logo/{winkel}_tag.png"]
              h3.pgprice     → "3.99"
        """
        results = []

        from services.unit_normalizer import parse_pgkgprice

        for entry in soup.find_all(class_="product-entry"):
            raw_name = entry.get("data-name", "").strip()
            if not raw_name:
                continue
            name = self._clean_product_name(raw_name)

            for item in entry.find_all(class_="cbp-pgitem"):
                # Winkelnaam uit logo-afbeelding: /img/shops_logo/hoogvliet_tag.png
                logo_img = item.find("img", src=re.compile(r"/img/shops_logo/"))
                if not logo_img:
                    continue
                src = logo_img.get("src", "")
                shop_raw = re.sub(r"_tag\.png.*", "", src.split("/")[-1])
                store_slug = self._map_store_name(shop_raw)
                if not store_slug:
                    continue

                price_el = item.find(class_="pgprice")
                if not price_el:
                    continue
                price_cents = self._price_str_to_cents(price_el.get_text(strip=True))
                if price_cents <= 0:
                    continue

                # Eenheidsprijs uit pgkgprice: "(26.60/liter)"
                unit_price_cents, unit_label = None, None
                kgprice_el = item.find(class_="pgkgprice")
                if kgprice_el:
                    unit_price_cents, unit_label = parse_pgkgprice(
                        kgprice_el.get_text(strip=True)
                    )

                results.append(ProductScraped(
                    store_slug=store_slug,
                    store_product_id=f"{name[:40]}_{store_slug}",
                    name=name.title(),
                    category_slug=category_slug,
                    price_cents=price_cents,
                    unit_price_cents=unit_price_cents,
                    unit_label=unit_label,
                    url=f"{BASE_URL}/product.php?keyword={quote_plus(query)}",
                ))

        return results

    def _clean_product_name(self, name: str) -> str:
        """Verwijder promotiesuffixen zoals 'vandaag', 'vanaf 7 apr' uit naam."""
        # "sprayvandaag" → "spray", "rollervanaf 7 apr" → "roller"
        name = re.sub(r"vandaag\s*$", "", name, flags=re.IGNORECASE).strip()
        name = re.sub(r"vanaf\s+\d+\s+\w+\s*$", "", name, flags=re.IGNORECASE).strip()
        return name

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
