"""
Haal prijzen op via supermarktscanner.nl voor alle of specifieke categorieën.
Gebruik:
  python scripts/run_scrapers.py                  # Alle categorieën
  python scripts/run_scrapers.py deodorant        # Alleen deodorant
  python scripts/run_scrapers.py koffie_thee boter  # Specifieke categorieën
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from config import CATEGORIES


async def main() -> None:
    from database import init_db
    await init_db()

    from services.cache_service import _run_full_scrape
    from scrapers.supermarktscanner import SupermarktScannerScraper
    from services.price_service import upsert_product
    from services.cache_service import _ensure_store
    from config import settings, STORES
    from database import AsyncSessionLocal
    from sqlalchemy import select
    from models.product import Store
    from datetime import datetime

    # Bepaal welke categorieën
    requested = sys.argv[1:]
    if requested:
        unknown = [c for c in requested if c not in CATEGORIES]
        if unknown:
            print(f"Onbekende categorieën: {', '.join(unknown)}")
            print(f"Beschikbaar: {', '.join(CATEGORIES.keys())}")
            sys.exit(1)
        categories = {k: CATEGORIES[k] for k in requested}
    else:
        categories = CATEGORIES

    print(f"▶ Ophalen via supermarktscanner.nl")
    print(f"  Categorieën: {', '.join(categories.keys())}\n")

    scraper = SupermarktScannerScraper(request_delay_ms=settings.scraper_request_delay_ms)
    total_ok = 0
    total_err = 0

    async with AsyncSessionLocal() as db:
        for slug, info in STORES.items():
            await _ensure_store(db, slug, info)

        result = await db.execute(select(Store))
        stores_by_slug = {s.slug: s.id for s in result.scalars().all()}

        for cat_slug, cat_info in categories.items():
            for query in cat_info.get("queries", [])[:1]:
                print(f"  Zoeken: '{query}' ({cat_info['label']})...")
                count = 0
                try:
                    async for product in scraper.search(query, cat_slug):
                        store_id = stores_by_slug.get(product.store_slug)
                        if not store_id:
                            store_info_dyn = STORES.get(product.store_slug, {
                                "display_name": product.store_slug.replace("_", " ").title(),
                                "type": "supermarket",
                                "color": "#999999",
                            })
                            store = await _ensure_store(db, product.store_slug, store_info_dyn)
                            store_id = store.id
                            stores_by_slug[product.store_slug] = store_id
                        try:
                            await upsert_product(db, product, store_id)
                            count += 1
                            total_ok += 1
                        except Exception as e:
                            total_err += 1
                    print(f"  ✓ {count} prijzen opgeslagen\n")
                except Exception as e:
                    print(f"  ✗ Fout: {type(e).__name__}: {e}\n")
                    total_err += 1

        result = await db.execute(select(Store))
        for store in result.scalars().all():
            store.last_scraped = datetime.utcnow()
            store.scrape_status = "ok" if total_err == 0 else "partial"
        await db.commit()

    print(f"Klaar: {total_ok} prijzen opgeslagen, {total_err} fouten")


if __name__ == "__main__":
    asyncio.run(main())
