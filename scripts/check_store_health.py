"""
Test of elke scraper bereikbaar is.
Gebruik: python scripts/check_store_health.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

SCRAPER_MAP = {
    "albert_heijn": ("scrapers.albert_heijn", "AlbertHeijnScraper"),
    "jumbo": ("scrapers.jumbo", "JumboScraper"),
    "lidl": ("scrapers.lidl", "LidlScraper"),
    "dirk": ("scrapers.dirk", "DirkScraper"),
    "plus": ("scrapers.plus", "PlusScraper"),
    "kruidvat": ("scrapers.kruidvat", "KruidvatScraper"),
    "etos": ("scrapers.etos", "EtosScraper"),
    "trekpleister": ("scrapers.trekpleister", "TrekpleisterScraper"),
}


async def check_all() -> None:
    print("PrijsScanner — Winkel gezondheidscheck\n")
    results = []
    for slug, (module_path, class_name) in SCRAPER_MAP.items():
        import importlib
        try:
            mod = importlib.import_module(module_path)
            ScraperClass = getattr(mod, class_name)
            scraper = ScraperClass()
            ok = await scraper.health_check()
            if hasattr(scraper, "close"):
                await scraper.close()
            status = "✅ OK" if ok else "❌ Niet bereikbaar"
        except Exception as e:
            status = f"❌ Fout: {e}"
        results.append((slug, status))
        print(f"  {status:<30} {slug}")

    print(f"\n{sum(1 for _, s in results if '✅' in s)}/{len(results)} winkels bereikbaar")


if __name__ == "__main__":
    asyncio.run(check_all())
