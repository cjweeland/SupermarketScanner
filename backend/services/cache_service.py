"""
Cache- en refresh-service: beheert de APScheduler job voor supermarktscanner.nl.
"""
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings, STORES, CATEGORIES
from database import AsyncSessionLocal
from models.product import Store
from services.price_service import upsert_product

logger = logging.getLogger(__name__)


async def scrape_store(store_slug: str) -> None:
    """
    Wordt aangeroepen vanuit de API voor handmatige refresh van één winkel.
    Omdat supermarktscanner.nl alle winkels tegelijk teruggeeft, triggeren
    we altijd een volledige scrape van alle categorieën.
    """
    logger.info("Refresh gestart (via supermarktscanner.nl) voor winkel: %s", store_slug)
    await _run_full_scrape()


async def _run_full_scrape() -> None:
    """Scrape alle categorieën via supermarktscanner.nl en sla op."""
    from scrapers.supermarktscanner import SupermarktScannerScraper

    scraper = SupermarktScannerScraper(request_delay_ms=settings.scraper_request_delay_ms)

    async with AsyncSessionLocal() as db:
        # Zorg dat alle store-records bestaan
        for slug, info in STORES.items():
            await _ensure_store(db, slug, info)

        # Haal store-IDs op
        result = await db.execute(select(Store))
        stores_by_slug = {s.slug: s.id for s in result.scalars().all()}

        total_ok = 0
        total_err = 0

        for cat_slug, cat_info in CATEGORIES.items():
            for query in cat_info.get("queries", [])[:1]:  # 1 query per categorie
                logger.info("Scraping: '%s' (categorie: %s)", query, cat_slug)
                try:
                    async for product in scraper.search(query, cat_slug):
                        store_id = stores_by_slug.get(product.store_slug)
                        if not store_id:
                            # Winkel niet in config — dynamisch toevoegen
                            store_info = STORES.get(product.store_slug, {
                                "display_name": product.store_slug.replace("_", " ").title(),
                                "type": "supermarket",
                                "color": "#999999",
                            })
                            store = await _ensure_store(db, product.store_slug, store_info)
                            store_id = store.id
                            stores_by_slug[product.store_slug] = store_id

                        try:
                            await upsert_product(db, product, store_id)
                            total_ok += 1
                        except Exception as e:
                            logger.debug("Fout bij opslaan product: %s", e)
                            total_err += 1
                except Exception as e:
                    logger.warning("Scrape fout voor '%s': %s: %s", query, type(e).__name__, e)
                    total_err += 1

        # Update scrape-status voor alle winkels
        result = await db.execute(select(Store))
        for store in result.scalars().all():
            store.last_scraped = datetime.utcnow()
            store.scrape_status = "ok" if total_err == 0 else "partial"
        await db.commit()

    logger.info("Scrape klaar: %d producten opgeslagen, %d fouten", total_ok, total_err)


async def _ensure_store(db: AsyncSession, slug: str, store_info: dict) -> Store:
    result = await db.execute(select(Store).where(Store.slug == slug))
    store = result.scalar_one_or_none()
    if store is None:
        store = Store(
            slug=slug,
            display_name=store_info.get("display_name", slug),
            type=store_info.get("type", "supermarket"),
            color=store_info.get("color", "#999999"),
            scrape_status="pending",
        )
        db.add(store)
        await db.flush()
    return store


def setup_scheduler() -> AsyncIOScheduler:
    """Scrape elke 4 uur alle categorieën opnieuw via supermarktscanner.nl."""
    import random
    scheduler = AsyncIOScheduler()
    jitter = random.randint(0, 15)
    scheduler.add_job(
        _run_full_scrape,
        "interval",
        hours=settings.cache_ttl_supermarket_hours,
        minutes=jitter,
        id="scrape_supermarktscanner",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("Scraper job: elke %dh + %dm (supermarktscanner.nl)", settings.cache_ttl_supermarket_hours, jitter)
    return scheduler
