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

# Categorieën per winkeltype
SUPERMARKET_CATEGORIES = {
    "vlees_vleeswaren": {
        "label": "Vlees & vleeswaren",
        "queries": ["kipfilet", "gehakt", "gekookte worst", "kipfilet vleeswaren"],
        "icon": "🥩",
    },
    "kaas": {
        "label": "Kaas",
        "queries": ["kaas blok", "geraspte kaas", "kaas 48+"],
        "icon": "🧀",
    },
    "koffie_thee": {
        "label": "Koffie & thee",
        "queries": ["Douwe Egberts koffie", "thee", "koffie"],
        "icon": "☕",
    },
    "wasmiddel": {
        "label": "Wasmiddel & afwasmiddel",
        "queries": ["wasmiddel", "afwasmiddel", "vaatwastabletten"],
        "icon": "🫧",
    },
    "pasta_rijst_sauzen": {
        "label": "Pasta, rijst & sauzen",
        "queries": ["pasta", "rijst", "pastasaus", "tomatensaus"],
        "icon": "🍝",
    },
    "ontbijtgranen_muesli": {
        "label": "Ontbijtgranen & muesli",
        "queries": ["muesli", "cornflakes", "havermout", "ontbijtgranen"],
        "icon": "🥣",
    },
    "boter": {
        "label": "Boter",
        "queries": ["Flower Farm boter", "roomboter", "boter"],
        "icon": "🧈",
    },
    "yoghurt_kwark": {
        "label": "Yoghurt & kwark",
        "queries": ["yoghurt", "kwark", "magere kwark"],
        "icon": "🥛",
    },
    "toiletpapier": {
        "label": "Toiletpapier & keukenpapier",
        "queries": ["toiletpapier", "keukenpapier", "wc papier"],
        "icon": "🧻",
    },
}

DRUGSTORE_CATEGORIES = {
    "shampoo_conditioner": {
        "label": "Shampoo & conditioner",
        "queries": ["shampoo", "conditioner"],
        "icon": "🧴",
    },
    "douchegel_zeep": {
        "label": "Douchegel & zeep",
        "queries": ["douchegel", "zeep", "handzeep"],
        "icon": "🚿",
    },
    "deodorant": {
        "label": "Deodorant",
        "queries": ["deodorant", "deo"],
        "icon": "💨",
    },
    "tandpasta_tandenborstels": {
        "label": "Tandpasta & tandenborstels",
        "queries": ["tandpasta", "tandenborstel", "elektrische tandenborstel"],
        "icon": "🦷",
    },
    "wasmiddel_wasverzachter": {
        "label": "Wasmiddel & wasverzachter",
        "queries": ["wasmiddel", "wasverzachter", "waspoeder"],
        "icon": "🧺",
    },
    "afwasmiddel_schoonmaakmiddelen": {
        "label": "Afwasmiddel & schoonmaakmiddelen",
        "queries": ["afwasmiddel", "schoonmaakmiddel", "allesreiniger"],
        "icon": "🧹",
    },
    "billendoekjes": {
        "label": "Billendoekjes",
        "queries": ["billendoekjes", "babydoekjes"],
        "icon": "🍼",
    },
    "baby_olie": {
        "label": "Baby-olie",
        "queries": ["baby olie", "babyolie"],
        "icon": "🫙",
    },
    "luiers": {
        "label": "Luiers",
        "queries": ["luiers", "pampers", "luier"],
        "icon": "👶",
    },
    "baby_shampoo": {
        "label": "Baby-shampoo",
        "queries": ["baby shampoo", "babyshampoo"],
        "icon": "🍶",
    },
    "baby_douchezeep": {
        "label": "Baby-douchezeep",
        "queries": ["baby douchezeep", "baby douchegel"],
        "icon": "🛁",
    },
    "vaatwastabletten": {
        "label": "Vaatwastabletten",
        "queries": ["vaatwastabletten", "vaatwas", "finish tabletten"],
        "icon": "🍽️",
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
