from pydantic_settings import BaseSettings
from typing import Dict


class Settings(BaseSettings):
    backend_port: int = 8000
    database_url: str = "sqlite+aiosqlite:///./prices.db"
    cache_ttl_supermarket_hours: int = 4
    scraper_request_delay_ms: int = 300
    log_level: str = "INFO"
    playwright_headless: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Eenheid per categorie voor eenheidsprijs-weergave
CATEGORY_UNIT_MAP: Dict[str, str] = {
    "vlees_vleeswaren": "100g",
    "kaas": "100g",
    "koffie_thee": "100g",
    "wasmiddel": "100ml",
    "pasta_rijst_sauzen": "100g",
    "ontbijtgranen_muesli": "100g",
    "boter": "100g",
    "yoghurt_kwark": "100g",
    "toiletpapier": "rol",
    "deodorant": "100ml",
}

# Alle productcategorieën met zoektermen voor supermarktscanner.nl
CATEGORIES = {
    "vlees_vleeswaren": {
        "label": "Vlees & vleeswaren",
        "queries": ["kipfilet", "gehakt", "gekookte worst"],
        "icon": "🥩",
    },
    "kaas": {
        "label": "Kaas",
        "queries": ["kaas blok", "geraspte kaas"],
        "icon": "🧀",
    },
    "koffie_thee": {
        "label": "Koffie & thee",
        "queries": ["Douwe Egberts koffie", "thee"],
        "icon": "☕",
    },
    "wasmiddel": {
        "label": "Wasmiddel & afwasmiddel",
        "queries": ["wasmiddel", "vaatwastabletten"],
        "icon": "🫧",
    },
    "pasta_rijst_sauzen": {
        "label": "Pasta, rijst & sauzen",
        "queries": ["pasta", "rijst", "pastasaus"],
        "icon": "🍝",
    },
    "ontbijtgranen_muesli": {
        "label": "Ontbijtgranen & muesli",
        "queries": ["muesli", "havermout"],
        "icon": "🥣",
    },
    "boter": {
        "label": "Boter",
        "queries": ["Flower Farm boter", "roomboter"],
        "icon": "🧈",
    },
    "yoghurt_kwark": {
        "label": "Yoghurt & kwark",
        "queries": ["yoghurt", "kwark"],
        "icon": "🥛",
    },
    "toiletpapier": {
        "label": "Toiletpapier & keukenpapier",
        "queries": ["toiletpapier", "keukenpapier"],
        "icon": "🧻",
    },
    "deodorant": {
        "label": "Deodorant",
        "queries": ["Dove deodorant"],
        "icon": "💨",
    },
}

# Voor backwards-compatibiliteit met bestaande code
SUPERMARKET_CATEGORIES = CATEGORIES
DRUGSTORE_CATEGORIES = {}
ALL_CATEGORIES = CATEGORIES

# Winkels die op supermarktscanner.nl staan
# Slugs worden dynamisch ontdekt via de scraper — dit zijn bekende winkels
STORES = {
    "albert_heijn": {"display_name": "Albert Heijn", "type": "supermarket", "color": "#00ADE6"},
    "jumbo":         {"display_name": "Jumbo",        "type": "supermarket", "color": "#FFC800"},
    "plus":          {"display_name": "Plus",         "type": "supermarket", "color": "#E4002B"},
    "lidl":          {"display_name": "Lidl",         "type": "supermarket", "color": "#0050AA"},
    "dirk":          {"display_name": "Dirk",         "type": "supermarket", "color": "#E30613"},
    "aldi":          {"display_name": "Aldi",         "type": "supermarket", "color": "#1A4F9F"},
    "coop":          {"display_name": "Coop",         "type": "supermarket", "color": "#E2001A"},
    "hoogvliet":     {"display_name": "Hoogvliet",    "type": "supermarket", "color": "#E4002B"},
    "jan_linders":   {"display_name": "Jan Linders",  "type": "supermarket", "color": "#00853E"},
    "poiesz":        {"display_name": "Poiesz",       "type": "supermarket", "color": "#E4002B"},
    "dekamarkt":     {"display_name": "DekaMarkt",    "type": "supermarket", "color": "#004B98"},
    "spar":          {"display_name": "Spar",         "type": "supermarket", "color": "#007A33"},
}

SUPERMARKET_STORE_SLUGS = list(STORES.keys())
DRUGSTORE_STORE_SLUGS = []
