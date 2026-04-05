from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.product import Product
from models.schemas import CategoryOut
from config import SUPERMARKET_CATEGORIES, DRUGSTORE_CATEGORIES

router = APIRouter()


@router.get("/categories", response_model=list[CategoryOut], summary="Beschikbare productcategorieën")
async def get_categories(db: AsyncSession = Depends(get_db)) -> list[CategoryOut]:
    # Haal productaantallen op per categorie
    result = await db.execute(
        select(Product.category_slug, func.count(Product.id).label("count"))
        .group_by(Product.category_slug)
    )
    counts = {row.category_slug: row.count for row in result}

    categories: list[CategoryOut] = []

    for slug, info in SUPERMARKET_CATEGORIES.items():
        categories.append(CategoryOut(
            slug=slug,
            label=info["label"],
            icon=info["icon"],
            store_type="supermarket",
            product_count=counts.get(slug, 0),
        ))

    for slug, info in DRUGSTORE_CATEGORIES.items():
        categories.append(CategoryOut(
            slug=slug,
            label=info["label"],
            icon=info["icon"],
            store_type="drugstore",
            product_count=counts.get(slug, 0),
        ))

    return categories
