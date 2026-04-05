# 🛒 PrijsScanner

Vergelijk supermarkt- en drogistprijzen in Nederland. Werkt op Windows, Mac én iPhone (PWA).

**Winkels:** Albert Heijn · Jumbo · Lidl · Dirk · Plus · Kruidvat · Trekpleister · Etos

---

## Snel starten

```bash
# Clone / open de map
cd SupermarketScanner

# Start in één commando (dev-modus)
./run.sh

# Of voor iPhone-gebruik op het thuisnetwerk:
./run.sh prod
```

Daarna open je `http://<laptop-IP>:8000` in Safari op iPhone → **Deel → Zet op beginscherm**.

---

## Handmatige installatie

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium         # Eenmalig, ~130MB

# Database aanmaken
python -c "import asyncio; from database import init_db; asyncio.run(init_db())"
python ../scripts/seed_categories.py

# Start backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

API-documentatie: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev     # Dev-server op http://localhost:5173
```

### Productie (frontend ingebakken in backend)

```bash
cd frontend
npm run build           # Output → backend/static/
cd ../backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## Prijzen ophalen

Na het starten zijn er nog geen prijzen in de database. Start een scan:

```bash
# Alle winkels scannen
python scripts/run_scrapers.py

# Één winkel
python scripts/run_scrapers.py albert_heijn

# Meerdere winkels
python scripts/run_scrapers.py jumbo kruidvat

# Winkelstatus controleren
python scripts/check_store_health.py
```

De app heeft ook een **automatisch refresh schema**:
- API-winkels (AH, Jumbo, Kruidvat): elke **4 uur**
- Playwright-winkels (Lidl, Plus, Dirk, Etos, Trekpleister): elke **6 uur**

---

## Configuratie

Kopieer `.env.example` naar `backend/.env`:

```bash
cp .env.example backend/.env
```

| Variabele | Standaard | Omschrijving |
|---|---|---|
| `BACKEND_PORT` | `8000` | Poort voor de backend |
| `DATABASE_URL` | `sqlite+aiosqlite:///./prices.db` | Database locatie |
| `CACHE_TTL_SUPERMARKET_HOURS` | `4` | Versheid supermarktprijzen |
| `CACHE_TTL_DRUGSTORE_HOURS` | `6` | Versheid drogistprijzen |
| `SCRAPER_REQUEST_DELAY_MS` | `300` | Vertraging tussen requests |
| `PLAYWRIGHT_HEADLESS` | `true` | Browser zichtbaar tijdens scrapen? |

---

## Productcategorieën

### 🛒 Supermarkt
- Vlees & vleeswaren (kipfilet, gehakt, gekookte worst)
- Kaas (blokken, geraspt)
- Koffie (Douwe Egberts) & thee
- Wasmiddel, afwasmiddel & vaatwastabletten
- Pasta, rijst & sauzen
- Ontbijtgranen & muesli
- Boter (Flower Farm)
- Yoghurt & kwark
- Toiletpapier & keukenpapier

### 💊 Drogist
- Shampoo & conditioner
- Douchegel & zeep
- Deodorant
- Tandpasta & tandenborstels
- Wasmiddel & wasverzachter
- Afwasmiddel & schoonmaakmiddelen
- Billendoekjes
- Baby-olie, baby-shampoo, baby-douchezeep
- Luiers
- Vaatwastabletten

---

## Architectuur

```
backend/
  main.py              FastAPI app
  scrapers/            Één scraper per winkel
  services/
    unit_normalizer.py  Prijzen per 100g / 100ml / stuk
    price_service.py    Vergelijkingslogica
    cache_service.py    APScheduler refresh-jobs
  api/                 REST endpoints
  models/              SQLAlchemy ORM + Pydantic schemas

frontend/
  src/
    views/             HomeView, SearchView, CategoryView, StoresView
    components/        CompareTable, PriceCell, StoreFilterBar, PromoBadge
    stores/            Pinia filters store
  vite.config.ts       PWA manifest + service worker
```

**Tech stack:** Python · FastAPI · SQLite · Playwright · Vue 3 · Vite · Tailwind CSS · PWA
