"""
Normaliseert producthoeveelheden naar een basisunit (gram, ml of stuks)
en berekent eenheidsprijzen voor vergelijking.
"""
import re
from dataclasses import dataclass
from typing import Optional

# Synoniemen → basisunit
WEIGHT_UNITS = {
    "g": 1.0, "gr": 1.0, "gram": 1.0, "grams": 1.0,
    "kg": 1000.0, "kilogram": 1000.0, "kilo": 1000.0,
    "mg": 0.001, "milligram": 0.001,
}

VOLUME_UNITS = {
    "ml": 1.0, "milliliter": 1.0, "millilitre": 1.0,
    "cl": 10.0, "centiliter": 10.0,
    "dl": 100.0, "deciliter": 100.0,
    "l": 1000.0, "liter": 1000.0, "litre": 1000.0, "ltr": 1000.0,
}

COUNT_UNITS = {
    "stuks": 1.0, "stuk": 1.0, "st": 1.0, "stks": 1.0,
    "tabs": 1.0, "tab": 1.0, "tabletten": 1.0, "tablet": 1.0,
    "capsules": 1.0, "capsule": 1.0, "caps": 1.0,
    "stuks": 1.0, "vel": 1.0,
    "x": 1.0,  # fallback voor "12x"
    "pak": 1.0, "pack": 1.0,
    "paar": 1.0,
}

ROLL_UNITS = {
    "rol": 1.0, "rollen": 1.0, "roll": 1.0, "rolls": 1.0,
    "vellen": 1.0,  # soms weergegeven als "vellen per rol"
}

ALL_UNITS = {**WEIGHT_UNITS, **VOLUME_UNITS, **COUNT_UNITS, **ROLL_UNITS}


@dataclass
class NormalizedQuantity:
    value: float               # hoeveelheid in basisunit
    base_unit: str             # "g" | "ml" | "stuks" | "rol"
    original_str: str          # originele string, bijv. "2 x 400ml"
    multiplier: int = 1        # multi-pack factor


# Regex patronen
# Patroon voor "2 x 400ml", "6x1l", "4 x 150 g", "3X500ML"
MULTIPACK_RE = re.compile(
    r"(\d+)\s*[xX×]\s*(\d+(?:[.,]\d+)?)\s*([a-zA-Z]+)",
    re.IGNORECASE,
)
# Patroon voor enkelvoudige hoeveelheid: "500g", "1,5 liter", "200 ml"
SINGLE_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*([a-zA-Z]+)",
    re.IGNORECASE,
)


def _parse_number(s: str) -> float:
    return float(s.replace(",", "."))


def _resolve_unit(unit_str: str) -> tuple[Optional[float], Optional[str]]:
    """Geeft (factor, base_unit) terug of (None, None) als niet herkend."""
    u = unit_str.lower().rstrip(".")
    if u in WEIGHT_UNITS:
        return WEIGHT_UNITS[u], "g"
    if u in VOLUME_UNITS:
        return VOLUME_UNITS[u], "ml"
    if u in ROLL_UNITS:
        return ROLL_UNITS[u], "rol"
    if u in COUNT_UNITS:
        return COUNT_UNITS[u], "stuks"
    return None, None


def normalize(size_str: str) -> Optional[NormalizedQuantity]:
    """
    Parseer een grootte-string en geeft NormalizedQuantity terug, of None als parsing mislukt.

    Voorbeelden:
        "500g" → NormalizedQuantity(500, "g", "500g")
        "2 x 400ml" → NormalizedQuantity(800, "ml", "2 x 400ml", multiplier=2)
        "1,5 liter" → NormalizedQuantity(1500, "ml", "1,5 liter")
        "12 stuks" → NormalizedQuantity(12, "stuks", "12 stuks")
    """
    if not size_str:
        return None
    s = size_str.strip()

    # Probeer multi-pack patroon eerst
    m = MULTIPACK_RE.search(s)
    if m:
        count = int(m.group(1))
        amount = _parse_number(m.group(2))
        unit_str = m.group(3)
        factor, base_unit = _resolve_unit(unit_str)
        if factor is not None:
            return NormalizedQuantity(
                value=count * amount * factor,
                base_unit=base_unit,
                original_str=s,
                multiplier=count,
            )

    # Probeer enkelvoudig patroon
    m = SINGLE_RE.search(s)
    if m:
        amount = _parse_number(m.group(1))
        unit_str = m.group(2)
        factor, base_unit = _resolve_unit(unit_str)
        if factor is not None:
            return NormalizedQuantity(
                value=amount * factor,
                base_unit=base_unit,
                original_str=s,
            )

    return None


def compute_unit_price(price_cents: int, normalized: NormalizedQuantity) -> tuple[int, str]:
    """
    Berekent eenheidsprijs in centen en de bijbehorende label.

    Returns:
        (unit_price_cents, unit_label)
        bijv. (160, "per 100g"), (45, "per 100ml"), (35, "per stuk")
    """
    v = normalized.value
    bu = normalized.base_unit

    if v <= 0:
        return 0, f"per {bu}"

    if bu == "g":
        unit_price = round(price_cents / v * 100)
        return unit_price, "per 100g"
    elif bu == "ml":
        unit_price = round(price_cents / v * 100)
        return unit_price, "per 100ml"
    elif bu == "rol":
        unit_price = round(price_cents / v)
        return unit_price, "per rol"
    elif bu == "stuks":
        unit_price = round(price_cents / v)
        return unit_price, "per stuk"
    else:
        unit_price = round(price_cents / v)
        return unit_price, f"per {bu}"


def format_unit_price(unit_price_cents: int, unit_label: str) -> str:
    """Geeft bijv. '€1,60 per 100g' terug."""
    euros = unit_price_cents / 100
    return f"€{euros:,.2f} {unit_label}".replace(",", "X").replace(".", ",").replace("X", ".")
