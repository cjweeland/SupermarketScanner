"""
Handmatige scraper-trigger voor één of alle winkels.
Gebruik:
  python scripts/run_scrapers.py                    # Alle winkels
  python scripts/run_scrapers.py albert_heijn       # Alleen Albert Heijn
  python scripts/run_scrapers.py jumbo kruidvat     # Specifieke winkels
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from config import STORES


async def main() -> None:
    from database import init_db
    await init_db()

    from services.cache_service import scrape_store

    slugs = sys.argv[1:] if len(sys.argv) > 1 else list(STORES.keys())

    # Valideer slugs
    unknown = [s for s in slugs if s not in STORES]
    if unknown:
        print(f"Onbekende winkels: {', '.join(unknown)}")
        print(f"Beschikbaar: {', '.join(STORES.keys())}")
        sys.exit(1)

    print(f"Start scraping van: {', '.join(slugs)}\n")

    for slug in slugs:
        print(f"▶ {STORES[slug]['display_name']}...")
        try:
            await scrape_store(slug)
            print(f"  ✓ Klaar\n")
        except Exception as e:
            print(f"  ✗ Fout: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
