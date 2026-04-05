"""
Zaai de winkel-records in de database en start de eerste scan voor alle categorieën.
Gebruik: python scripts/seed_categories.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from database import init_db, AsyncSessionLocal
from config import STORES
from models.product import Store
from sqlalchemy import select


async def seed_stores() -> None:
    await init_db()
    async with AsyncSessionLocal() as db:
        for slug, info in STORES.items():
            result = await db.execute(select(Store).where(Store.slug == slug))
            store = result.scalar_one_or_none()
            if store is None:
                store = Store(
                    slug=slug,
                    display_name=info["display_name"],
                    type=info["type"],
                    color=info.get("color", "#999999"),
                    scrape_status="pending",
                )
                db.add(store)
                print(f"  ✓ Winkel aangemaakt: {info['display_name']}")
            else:
                print(f"  - Winkel bestaat al: {info['display_name']}")
        await db.commit()
    print("\nWinkels succesvol aangemaakt in de database.")


if __name__ == "__main__":
    asyncio.run(seed_stores())
