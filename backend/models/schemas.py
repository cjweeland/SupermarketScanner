from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class PromoOut(BaseModel):
    type: str
    description: str
    promo_price_cents: Optional[int] = None
    requires_membership: bool = False
    valid_until: Optional[datetime] = None

    model_config = {"from_attributes": True}


class StorePriceOut(BaseModel):
    store_slug: str
    store_name: str
    store_color: str
    price_cents: int
    price_formatted: str
    unit_price_cents: Optional[int] = None
    unit_price_formatted: Optional[str] = None
    unit_label: Optional[str] = None
    promotion: Optional[PromoOut] = None
    product_url: Optional[str] = None
    image_url: Optional[str] = None
    freshness: str = "live"  # live | stale


class ComparisonResultOut(BaseModel):
    product_name: str
    brand: Optional[str] = None
    category_slug: Optional[str] = None
    prices: list[StorePriceOut]
    best_value_store: Optional[str] = None
    best_value_after_promo_store: Optional[str] = None


class CompareResponseOut(BaseModel):
    data: list[ComparisonResultOut]
    meta: dict


class CategoryOut(BaseModel):
    slug: str
    label: str
    icon: str
    store_type: str  # supermarket | drugstore
    product_count: int = 0


class StoreStatusOut(BaseModel):
    slug: str
    display_name: str
    type: str
    color: str
    last_scraped: Optional[datetime] = None
    scrape_status: str
    product_count: int = 0


class ProductScraped(BaseModel):
    """Internal model used by scrapers to pass data to the DB layer."""
    store_slug: str
    store_product_id: str
    name: str
    brand: Optional[str] = None
    category_slug: Optional[str] = None
    image_url: Optional[str] = None
    url: Optional[str] = None
    quantity: Optional[float] = None
    quantity_unit: Optional[str] = None
    price_cents: int
    original_price_cents: Optional[int] = None
    promotion: Optional["PromoScraped"] = None


class PromoScraped(BaseModel):
    promo_type: str
    description: str
    promo_price_cents: Optional[int] = None
    requires_membership: bool = False
    valid_until: Optional[datetime] = None
