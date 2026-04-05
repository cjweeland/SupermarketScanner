"""
Cache- en refresh-service: beheert de APScheduler jobs per winkel.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings, STORES, SUPERMARKET_CATEGORIES, DRUGSTORE_CATEGORIES, ALL_CATEGORIES
from database import AsyncSessionLocal
from models.product import Store
from services.price_service import upsert_product

logger = logging.getLogger(__name__)

# Scraper-klasse mapping (lazy import om circulaire imports te vermijden)
SCRAPER_MAP = {
    "albert_heijn": "scrapers.albert_heijn:AlbertHeijnScraper",
    "jumbo": "scrapers.jumbo:JumboScraper",
    "lidl": "scrapers.lidl:LidlScraper",
    "dirk": "scrapers.dirk:DirkScraper",
    "plus": "scrapers.plus:PlusScraper",
    "kruidvat": "scrapers.kruidvat:KruidvatScraper",
    "etos": "scrapers.etos:EtosScraper",
    "trekpleister": "scrapers.trekpleister:TrekpleisterScraper",
}

# Interval per winkel in uren
SCRAPE_INTERVALS = {
    "albert_heijn": 4,
    "jumbo": 4,
    "kruidvat": 4,
    "lidl": 6,
    "plus": 6,
    "dirk": 6,
    "etos": 6,
    "trekpleister": 6,
}


def _import_scraper(path: str):
    module_path, class_name = path.rsplit(":", 1)
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


async def scrape_store(store_slug: str) -> None:
    """Scrape alle categorieën voor één winkel en sla resultaten op."""
    logger.info("Start scraping: %s", store_slug)
    store_info = STORES.get(store_slug)
    if not store_info:
        logger.error("Onbekende winkel: %s", store_slug)
        return

    scraper_path = SCRAPER_MAP.get(store_slug)
    if not scraper_path:
        logger.error("Geen scraper gevonden voor: %s", store_slug)
        return

    ScraperClass = _import_scraper(scraper_path)
    scraper = ScraperClass(request_delay_ms=settings.scraper_request_delay_ms)

    # Bepaal welke categorieën voor dit winkeltype
    if store_info["type"] == "supermarket":
        categories = SUPERMARKET_CATEGORIES
    else:
        categories = DRUGSTORE_CATEGORIES

    async with AsyncSessionLocal() as db:
        # Zorg dat Store-record bestaat
        store_obj = await _ensure_store(db, store_slug, store_info)
        store_id = store_obj.id

        success_count = 0
        error_count = 0

        for cat_slug, cat_info in categories.items():
            queries = cat_info.get("queries", [])
            # Neem de eerste 2 queries per categorie om belasting te beperken
            for query in queries[:2]:
                try:
                    async for product in scraper.search(query, cat_slug):
                        try:
                            await upsert_product(db, product, store_id)
                            success_count += 1
                        except Exception as e:
                            logger.debug("Fout bij opslaan product: %s", e)
                            error_count += 1
                except Exception as e:
                    logger.warning("Scrape fout voor %s/%s: %s", store_slug, query, e)
                    error_count += 1
                    continue

        # Update store status
        store_obj.last_scraped = datetime.utcnow()
        store_obj.scrape_status = "ok" if error_count == 0 else "partial"
        await db.commit()
        logger.info("Klaar met scraping %s: %d producten, %d fouten", store_slug, success_count, error_count)

    # Ruim scraper client op
    if hasattr(scraper, "close"):
        await scraper.close()


async def _ensure_store(db: AsyncSession, slug: str, store_info: dict) -> Store:
    result = await db.execute(select(Store).where(Store.slug == slug))
    store = result.scalar_one_or_none()
    if store is None:
        store = Store(
            slug=slug,
            display_name=store_info["display_name"],
            type=store_info["type"],
            color=store_info.get("color", "#999999"),
            scrape_status="pending",
        )
        db.add(store)
        await db.flush()
    return store


def setup_scheduler() -> AsyncIOScheduler:
    """Maak de APScheduler aan en configureer jobs per winkel."""
    import random
    scheduler = AsyncIOScheduler()

    for store_slug, interval_hours in SCRAPE_INTERVALS.items():
        # Jitter: random offset 0-15 minuten om gelijktijdige requests te vermijden
        jitter_minutes = random.randint(0, 15)

        scheduler.add_job(
            scrape_store,
            "interval",
            hours=interval_hours,
            minutes=jitter_minutes,
            args=[store_slug],
            id=f"scrape_{store_slug}",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info("Scraper job aangemaakt voor %s (elke %dh + %dm jitter)", store_slug, interval_hours, jitter_minutes)

    return scheduler
