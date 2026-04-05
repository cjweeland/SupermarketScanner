from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # supermarket | drugstore
    color: Mapped[str] = mapped_column(String(10), nullable=False, default="#999999")
    last_scraped: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    scrape_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    scrape_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    products: Mapped[list["Product"]] = relationship("Product", back_populates="store", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(Integer, ForeignKey("stores.id"), nullable=False)
    store_product_id: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    brand: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    category_slug: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quantity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quantity_unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    normalized_quantity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    normalized_unit: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # g | ml | stuks | rol
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    store: Mapped["Store"] = relationship("Store", back_populates="products")
    price_snapshots: Mapped[list["PriceSnapshot"]] = relationship(
        "PriceSnapshot", back_populates="product", cascade="all, delete-orphan"
    )
    promotions: Mapped[list["Promotion"]] = relationship(
        "Promotion", back_populates="product", cascade="all, delete-orphan"
    )


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    unit_label: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    product: Mapped["Product"] = relationship("Product", back_populates="price_snapshots")


class Promotion(Base):
    __tablename__ = "promotions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    promo_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    promo_price_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    requires_membership: Mapped[bool] = mapped_column(Boolean, default=False)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    product: Mapped["Product"] = relationship("Product", back_populates="promotions")
