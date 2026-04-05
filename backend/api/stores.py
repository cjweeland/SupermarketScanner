from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.product import Store, Product
from models.schemas import StoreStatusOut
from config import STORES
from services.cache_service import scrape_store

router = APIRouter()


@router.get("/stores", response_model=list[StoreStatusOut], summary="Status van alle winkels")
async def get_stores(db: AsyncSession = Depends(get_db)) -> list[StoreStatusOut]:
    # Haal store-records op
    stores_result = await db.execute(select(Store))
    stores_by_slug = {s.slug: s for s in stores_result.scalars().all()}

    # Product-aantallen per winkel
    counts_result = await db.execute(
        select(Store.slug, func.count(Product.id).label("count"))
        .join(Product, isouter=True)
        .group_by(Store.slug)
    )
    counts = {row.slug: row.count for row in counts_result}

    result: list[StoreStatusOut] = []
    for slug, store_info in STORES.items():
        store = stores_by_slug.get(slug)
        result.append(StoreStatusOut(
            slug=slug,
            display_name=store_info["display_name"],
            type=store_info["type"],
            color=store_info["color"],
            last_scraped=store.last_scraped if store else None,
            scrape_status=store.scrape_status if store else "pending",
            product_count=counts.get(slug, 0),
        ))

    return result


@router.post("/stores/{store_slug}/refresh", summary="Forceer een hernieuwde scan van een winkel")
async def refresh_store(
    store_slug: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    if store_slug not in STORES:
        raise HTTPException(status_code=404, detail=f"Winkel '{store_slug}' niet gevonden")

    background_tasks.add_task(scrape_store, store_slug)
    return {"message": f"Refresh gestart voor {STORES[store_slug]['display_name']}", "store": store_slug}
