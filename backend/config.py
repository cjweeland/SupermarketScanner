from pydantic_settings import BaseSettings
from typing import Dict


class Settings(BaseSettings):
    backend_port: int = 8000
    database_url: str = "sqlite+aiosqlite:///./prices.db"
    cache_ttl_supermarket_hours: int = 4
    cache_ttl_drugstore_hours: int = 6
    scraper_request_delay_ms: int = 300
    log_level: str = "INFO"
    playwright_headless: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Welke eenheid hoort bij welke categorie voor eenheidsprijs-weergave
CATEGORY_UNIT_MAP: Dict[str, str] = {
    # Supermarkt
    "vlees_vleeswaren": "100g",
    "kaas": "100g",
    "koffie_thee": "100g",
    "wasmiddel": "100ml",
    "pasta_rijst_sauzen": "100g",
    "ontbijtgranen_muesli": "100g",
    "boter": "100g",
    "yoghurt_kwark": "100g",
    "toiletpapier": "rol",
    # Drogist
    "shampoo_conditioner": "100ml",
    "douchegel_zeep": "100ml",
    "deodorant": "100ml",
    "tandpasta_tandenborstels": "100g",
    "wasmiddel_wasverzachter": "100ml",
    "afwasmiddel_schoonmaakmiddelen": "100ml",
    "billendoekjes": "stuk",
    "baby_olie": "100ml",
    "luiers": "stuk",
    "baby_shampoo": "100ml",
    "baby_douchezeep": "100ml",
    "vaatwastabletten": "stuk",
}

# Testmodus: één product voor alle winkels
# Dove deodorant wordt verkocht bij zowel supermarkten als drogisten
TEST_PRODUCT = {
    "query": "Dove deodorant",
    "category_slug": "deodorant",
}

# Categorieën per winkeltype (testmodus: alleen deodorant)
SUPERMARKET_CATEGORIES = {
    "deodorant": {
        "label": "Deodorant",
        "queries": ["Dove deodorant"],
        "icon": "💨",
    },
}

DRUGSTORE_CATEGORIES = {
    "deodorant": {
        "label": "Deodorant",
        "queries": ["Dove deodorant"],
        "icon": "💨",
    },
}

ALL_CATEGORIES = {**SUPERMARKET_CATEGORIES, **DRUGSTORE_CATEGORIES}

SUPERMARKET_STORE_SLUGS = ["albert_heijn", "jumbo", "lidl", "dirk", "plus"]
DRUGSTORE_STORE_SLUGS = ["kruidvat", "trekpleister", "etos"]

STORES = {
    "albert_heijn": {"display_name": "Albert Heijn", "type": "supermarket", "color": "#00ADE6"},
    "jumbo": {"display_name": "Jumbo", "type": "supermarket", "color": "#FFC800"},
    "lidl": {"display_name": "Lidl", "type": "supermarket", "color": "#0050AA"},
    "dirk": {"display_name": "Dirk", "type": "supermarket", "color": "#E30613"},
    "plus": {"display_name": "Plus", "type": "supermarket", "color": "#E4002B"},
    "kruidvat": {"display_name": "Kruidvat", "type": "drugstore", "color": "#DA291C"},
    "trekpleister": {"display_name": "Trekpleister", "type": "drugstore", "color": "#E4002B"},
    "etos": {"display_name": "Etos", "type": "drugstore", "color": "#00517F"},
}
