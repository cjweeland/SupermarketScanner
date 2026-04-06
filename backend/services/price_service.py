"""
Vergelijkingslogica: normaliseert prijzen en rangschikt producten per eenheid.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import settings, STORES, CATEGORY_UNIT_MAP
from models.product import Store, Product, PriceSnapshot, Promotion
from models.schemas import (
    ComparisonResultOut,
    StorePriceOut,
    PromoOut,
    CompareResponseOut,
)
from services.unit_normalizer import normalize, compute_unit_price

logger = logging.getLogger(__name__)


def _format_price(cents: int) -> str:
    return f"€{cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


async def upsert_product(db: AsyncSession, scraped, store_id: int) -> None:
    """Bewaar of update een gescraped product inclusief prijs en promotie."""
    from models.schemas import ProductScraped
    from services.unit_normalizer import normalize, compute_unit_price

    # Zoek bestaand product
    result = await db.execute(
        select(Product).where(
            Product.store_id == store_id,
            Product.store_product_id == scraped.store_product_id,
        )
    )
    product = result.scalar_one_or_none()

    # Normaliseer hoeveelheid
    normalized = normalize(scraped.quantity_unit or "") if scraped.quantity_unit else None

    if product is None:
        product = Product(
            store_id=store_id,
            store_product_id=scraped.store_product_id,
            name=scraped.name,
            brand=scraped.brand,
            category_slug=scraped.category_slug,
            image_url=scraped.image_url,
            url=scraped.url,
            quantity_unit=scraped.quantity_unit,
            normalized_quantity=normalized.value if normalized else None,
            normalized_unit=normalized.base_unit if normalized else None,
        )
        db.add(product)
        await db.flush()
    else:
        product.name = scraped.name
        product.brand = scraped.brand
        product.category_slug = scraped.category_slug
        product.image_url = scraped.image_url
        product.url = scraped.url
        product.quantity_unit = scraped.quantity_unit
        if normalized:
            product.normalized_quantity = normalized.value
            product.normalized_unit = normalized.base_unit
        product.updated_at = datetime.utcnow()

    # Eenheidsprijs: gebruik gescrapede waarde, anders berekenen uit hoeveelheid
    unit_price_cents = None
    unit_label = None
    if scraped.unit_price_cents and scraped.unit_price_cents > 0:
        unit_price_cents = scraped.unit_price_cents
        unit_label = scraped.unit_label
    elif normalized and scraped.price_cents > 0:
        unit_price_cents, unit_label = compute_unit_price(scraped.price_cents, normalized)

    # Prijs snapshot
    snapshot = PriceSnapshot(
        product_id=product.id,
        price_cents=scraped.price_cents,
        unit_price_cents=unit_price_cents,
        unit_label=unit_label,
        captured_at=datetime.utcnow(),
    )
    db.add(snapshot)

    # Verwijder oude actieve promoties
    existing_promos = await db.execute(
        select(Promotion).where(Promotion.product_id == product.id, Promotion.active == True)
    )
    for promo in existing_promos.scalars().all():
        promo.active = False

    # Nieuwe promotie opslaan
    if scraped.promotion:
        promo_obj = Promotion(
            product_id=product.id,
            promo_type=scraped.promotion.promo_type,
            description=scraped.promotion.description,
            promo_price_cents=scraped.promotion.promo_price_cents,
            requires_membership=scraped.promotion.requires_membership,
            valid_until=scraped.promotion.valid_until,
            active=True,
        )
        db.add(promo_obj)

    await db.commit()


async def compare_products(
    db: AsyncSession,
    query: str,
    category_slug: Optional[str],
    store_slugs: Optional[list[str]],
    limit: int = 20,
) -> CompareResponseOut:
    """
    Zoek producten bij meerdere winkels en geef een vergelijkingsoverzicht terug.
    """
    # Bepaal welke winkels meegenomen worden
    if store_slugs:
        store_filter = store_slugs
    else:
        store_filter = list(STORES.keys())

    # Haal stores op
    stores_result = await db.execute(
        select(Store).where(Store.slug.in_(store_filter))
    )
    stores_by_slug = {s.slug: s for s in stores_result.scalars().all()}

    # Zoek producten
    stmt = (
        select(Product)
        .join(Store)
        .where(Store.slug.in_(store_filter))
        .options(
            selectinload(Product.store),
            selectinload(Product.price_snapshots),
            selectinload(Product.promotions),
        )
    )
    if query:
        # Eenvoudige case-insensitive zoekterm
        stmt = stmt.where(Product.name.ilike(f"%{query}%"))
    if category_slug:
        stmt = stmt.where(Product.category_slug == category_slug)

    stmt = stmt.limit(200)
    result = await db.execute(stmt)
    products = result.scalars().all()

    # Groepeer op productnaam (heuristiek: verwijder winkelspecifieke variaties)
    # Simpele aanpak: groepeer per basisnaam × categorie, max 1 product per winkel
    groups: dict[str, dict[str, Product]] = {}
    for product in products:
        # Normaliseer naam als groeperingssleutel
        key = _normalize_product_name(product.name, product.category_slug)
        if key not in groups:
            groups[key] = {}
        store_slug = product.store.slug
        # Neem alleen het meest recente product per winkel per groep
        if store_slug not in groups[key]:
            groups[key][store_slug] = product
        else:
            existing = groups[key][store_slug]
            if product.updated_at and existing.updated_at and product.updated_at > existing.updated_at:
                groups[key][store_slug] = product

    # Bouw vergelijkingsresultaten
    comparison_results: list[ComparisonResultOut] = []

    for group_name, store_products in groups.items():
        prices_out: list[StorePriceOut] = []

        for store_slug, product in store_products.items():
            store_info = STORES.get(store_slug, {})

            # Nieuwste prijs snapshot
            latest_snapshot = None
            if product.price_snapshots:
                latest_snapshot = max(product.price_snapshots, key=lambda s: s.captured_at)

            if not latest_snapshot or latest_snapshot.price_cents <= 0:
                continue

            price_cents = latest_snapshot.price_cents

            # Actieve promoties
            active_promos = [p for p in product.promotions if p.active]
            promo_out = None
            if active_promos:
                promo = active_promos[0]
                promo_out = PromoOut(
                    type=promo.promo_type,
                    description=promo.description,
                    promo_price_cents=promo.promo_price_cents,
                    requires_membership=promo.requires_membership,
                    valid_until=promo.valid_until,
                )

            # Versheid check
            cache_ttl = timedelta(hours=settings.cache_ttl_supermarket_hours)
            is_stale = latest_snapshot.captured_at < datetime.utcnow() - cache_ttl

            prices_out.append(StorePriceOut(
                store_slug=store_slug,
                store_name=store_info.get("display_name", store_slug),
                store_color=store_info.get("color", "#999"),
                price_cents=price_cents,
                price_formatted=_format_price(price_cents),
                unit_price_cents=latest_snapshot.unit_price_cents,
                unit_price_formatted=(
                    _format_price(latest_snapshot.unit_price_cents) + f" {latest_snapshot.unit_label}"
                    if latest_snapshot.unit_price_cents and latest_snapshot.unit_label
                    else None
                ),
                unit_label=latest_snapshot.unit_label,
                promotion=promo_out,
                product_url=product.url,
                image_url=product.image_url,
                freshness="stale" if is_stale else "live",
            ))

        if len(prices_out) < 1:
            continue

        # Beste waarde bepalen (op eenheidsprijs, anders op absolute prijs)
        def unit_price_key(p: StorePriceOut) -> int:
            return p.unit_price_cents if p.unit_price_cents else p.price_cents

        def promo_price_key(p: StorePriceOut) -> int:
            if p.promotion and p.promotion.promo_price_cents:
                return p.promotion.promo_price_cents
            return unit_price_key(p)

        best = min(prices_out, key=unit_price_key)
        best_promo = min(prices_out, key=promo_price_key)

        # Zoek een representatieve productnaam
        sample_product = next(iter(store_products.values()))

        comparison_results.append(ComparisonResultOut(
            product_name=sample_product.name,
            brand=sample_product.brand,
            category_slug=sample_product.category_slug,
            prices=sorted(prices_out, key=unit_price_key),
            best_value_store=best.store_slug,
            best_value_after_promo_store=best_promo.store_slug,
        ))

    # Sorteer op aantal winkels (meest vertegenwoordigd eerst)
    comparison_results.sort(key=lambda r: len(r.prices), reverse=True)
    comparison_results = comparison_results[:limit]

    return CompareResponseOut(
        data=comparison_results,
        meta={
            "query": query,
            "category": category_slug,
            "stores_queried": store_filter,
            "total": len(comparison_results),
            "generated_at": datetime.utcnow().isoformat() + "Z",
        },
    )


def _normalize_product_name(name: str, category_slug: Optional[str]) -> str:
    """
    Vereenvoudigde naam-normalisatie voor product-groepering.
    Verwijdert getallen, gewichtsaanduidingen en winkelspecifieke suffixes.
    """
    import re
    n = name.lower().strip()
    # Verwijder gewicht/volume (bijv. "500g", "1,5l")
    n = re.sub(r"\d+[.,]?\d*\s*(g|gr|gram|kg|ml|l|liter|cl|stuks|stuk|st)\b", "", n)
    # Verwijder getallen die op zich staan
    n = re.sub(r"\b\d+\b", "", n)
    # Verwijder extra spaties
    n = re.sub(r"\s+", " ", n).strip()
    return f"{category_slug or ''}:{n}"
