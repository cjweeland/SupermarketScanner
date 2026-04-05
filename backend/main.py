"""
PrijsScanner backend — FastAPI applicatie.
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from database import init_db
from api.comparison import router as comparison_router
from api.categories import router as categories_router
from api.stores import router as stores_router
from services.cache_service import setup_scheduler

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("PrijsScanner backend wordt gestart...")
    await init_db()
    logger.info("Database geïnitialiseerd")

    scheduler = setup_scheduler()
    scheduler.start()
    logger.info("Scraper-scheduler gestart")

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("PrijsScanner backend gestopt")


app = FastAPI(
    title="PrijsScanner API",
    description="Vergelijk supermarkt- en drogistprijzen in Nederland",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: sta lokale frontend toe
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(comparison_router, prefix="/api/v1", tags=["Vergelijking"])
app.include_router(categories_router, prefix="/api/v1", tags=["Categorieën"])
app.include_router(stores_router, prefix="/api/v1", tags=["Winkels"])

# Statische frontend bestanden (na `npm run build`)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
    logger.info("Frontend bestanden geladen vanuit: %s", static_dir)
else:
    @app.get("/", tags=["Root"])
    async def root():
        return {
            "message": "PrijsScanner API is actief. Start de frontend met: cd frontend && npm run dev",
            "docs": "/docs",
            "api": "/api/v1/",
        }
