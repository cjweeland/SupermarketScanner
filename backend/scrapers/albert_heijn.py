"""
Albert Heijn scraper via de AH Mobile API.
Gebruikt een anoniem bearer token dat per sessie wordt opgehaald.
"""
import logging
from typing import AsyncIterator, Optional

import httpx

from models.schemas import ProductScraped, PromoScraped
from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

AUTH_URL = "https://api.ah.nl/mobile-auth/v1/auth/token/anonymous"
SEARCH_URL = "https://api.ah.nl/mobile-services/product/search/v2"
BONUS_URL = "https://api.ah.nl/mobile-services/bonuspage/v1/metadata"
PRODUCT_BASE_URL = "https://www.ah.nl/producten/product/"

HEADERS = {
    "x-application": "AHWEBSHOP",
    "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36",
    "Accept": "application/json",
}


class AlbertHeijnScraper(BaseScraper):
    store_slug = "albert_heijn"
    store_name = "Albert Heijn"

    def __init__(self, request_delay_ms: int = 300):
        super().__init__(request_delay_ms)
        self._token: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(headers=HEADERS, timeout=15)
        return self._client

    async def _get_token(self) -> str:
        if self._token:
            return self._token
        client = await self._get_client()
        resp = await client.post(AUTH_URL, json={"clientId": "appie"})
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        return self._token

    def _auth_headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    async def search(self, query: str, category_slug: str) -> AsyncIterator[ProductScraped]:
        client = await self._get_client()
        token = await self._get_token()
        page = 0

        while True:
            await self._delay()
            try:
                resp = await client.get(
                    SEARCH_URL,
                    params={"query": query, "size": 30, "page": page},
                    headers=self._auth_headers(token),
                )
                if resp.status_code == 401:
                    self._token = None
                    token = await self._get_token()
                    resp = await client.get(
                        SEARCH_URL,
                        params={"query": query, "size": 30, "page": page},
                        headers=self._auth_headers(token),
                    )
                resp.raise_for_status()
            except httpx.HTTPError as e:
                logger.error("AH search fout voor '%s': %s", query, e)
                break

            data = resp.json()
            cards = data.get("cards", [])
            if not cards:
                break

            for card in cards:
                product_data = card.get("products", [{}])[0] if card.get("products") else {}
                if not product_data:
                    # Sommige kaarten zijn banners of separators
                    p = card.get("card", {}).get("message") or card
                    if isinstance(p, dict) and "id" in p:
                        product_data = p
                    else:
                        continue

                try:
                    yield self._parse_product(product_data, category_slug)
                except Exception as e:
                    logger.debug("AH product parse fout: %s", e)
                    continue

            # Controleer of er meer pagina's zijn
            page_info = data.get("page", {})
            total_pages = page_info.get("totalPages", 1)
            if page + 1 >= total_pages:
                break
            page += 1

    def _parse_product(self, p: dict, category_slug: str) -> ProductScraped:
        product_id = str(p.get("webshopId") or p.get("id", ""))
        name = p.get("title", "")
        brand = p.get("brand", {}).get("name") if isinstance(p.get("brand"), dict) else p.get("brand")

        # Prijsinformatie
        price_info = p.get("price", {})
        price_now = price_info.get("now", 0)
        price_was = price_info.get("was")
        price_cents = self._float_to_cents(float(price_now))

        # Unit prijs wordt direct opgegeven door AH
        unit_desc = p.get("priceBeforeBonus") or p.get("unitPriceDescription")

        # Afbeelding
        images = p.get("images", [])
        image_url = images[0].get("url") if images else None
        if image_url and not image_url.startswith("http"):
            image_url = "https:" + image_url

        # Grootte
        size_str = p.get("unitSize") or p.get("descriptionHighlights") or ""
        if isinstance(size_str, list):
            size_str = " ".join(size_str)

        # Bonus/actie
        promotion = None
        bonus = p.get("bonus")
        if bonus:
            bonus_mechanism = bonus.get("mechanism", "")
            bonus_str = bonus.get("description", "Bonusaanbieding")
            promo_price = bonus.get("promotionPrice")
            promo_price_cents = self._float_to_cents(float(promo_price)) if promo_price else None
            promotion = PromoScraped(
                promo_type="bonus_card",
                description=f"Bonuskaart: {bonus_str}",
                promo_price_cents=promo_price_cents,
                requires_membership=True,
            )
        elif price_was and float(price_was) > float(price_now):
            original_cents = self._float_to_cents(float(price_was))
            korting = round((1 - float(price_now) / float(price_was)) * 100)
            promotion = PromoScraped(
                promo_type="percentage_off",
                description=f"{korting}% korting",
                promo_price_cents=price_cents,
            )

        url = None
        slug = p.get("slugifiedName") or p.get("descriptionFull", "").lower().replace(" ", "-")
        if product_id and slug:
            url = f"{PRODUCT_BASE_URL}{slug}/{product_id}"

        return ProductScraped(
            store_slug=self.store_slug,
            store_product_id=product_id,
            name=name,
            brand=brand,
            category_slug=category_slug,
            image_url=image_url,
            url=url,
            quantity=None,
            quantity_unit=size_str if size_str else None,
            price_cents=price_cents,
            promotion=promotion,
        )

    async def health_check(self) -> bool:
        try:
            await self._get_token()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
