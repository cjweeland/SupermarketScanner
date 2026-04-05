from typing import Optional
from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.schemas import CompareResponseOut
from services.price_service import compare_products
from services.cache_service import scrape_store

router = APIRouter()


@router.get("/compare", response_model=CompareResponseOut, summary="Vergelijk prijzen over meerdere winkels")
async def compare(
    background_tasks: BackgroundTasks,
    q: str = Query(..., description="Zoekterm, bijv. 'yoghurt' of 'Douwe Egberts'"),
    category: Optional[str] = Query(None, description="Categorieslug, bijv. 'koffie_thee'"),
    stores: Optional[str] = Query(None, description="Komma-gescheiden lijst van winkelslugs"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> CompareResponseOut:
    store_slugs = [s.strip() for s in stores.split(",")] if stores else None

    result = await compare_products(db, q, category, store_slugs, limit)

    # Als er verouderde data is, stuur een achtergrond-refresh op
    stale_stores = set()
    for comparison in result.data:
        for price in comparison.prices:
            if price.freshness == "stale":
                stale_stores.add(price.store_slug)

    for store_slug in stale_stores:
        background_tasks.add_task(scrape_store, store_slug)

    return result
