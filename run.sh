#!/usr/bin/env bash
# PrijsScanner opstartscript
# Gebruik: ./run.sh [dev|prod]
# - dev:  start backend + frontend devserver (standaard)
# - prod: bouw frontend en serveer via backend (geschikt voor iPhone op WiFi)

set -e

MODE="${1:-dev}"
BACKEND_DIR="$(cd "$(dirname "$0")/backend" && pwd)"
FRONTEND_DIR="$(cd "$(dirname "$0")/frontend" && pwd)"

# Kleur output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🛒 PrijsScanner opstarten (modus: ${MODE})${NC}\n"

# Controleer Python venv
if [ ! -d "$BACKEND_DIR/.venv" ]; then
    echo -e "${YELLOW}Python virtual environment aanmaken...${NC}"
    python3 -m venv "$BACKEND_DIR/.venv"
fi

# Activeer venv
source "$BACKEND_DIR/.venv/bin/activate"

# Installeer Python dependencies
echo -e "${BLUE}Python dependencies controleren...${NC}"
pip install -q -r "$BACKEND_DIR/requirements.txt"

# Playwright chromium installeren indien nodig
if ! python -c "from playwright.sync_api import sync_playwright; sync_playwright().__enter__().chromium.executable_path" &>/dev/null 2>&1; then
    echo -e "${BLUE}Playwright Chromium downloaden (eenmalig ~130MB)...${NC}"
    playwright install chromium
fi

# Database initialiseren / migreren
echo -e "${BLUE}Database initialiseren...${NC}"
cd "$BACKEND_DIR"
python -c "import asyncio; from database import init_db; asyncio.run(init_db())"
python "$BACKEND_DIR/../scripts/seed_categories.py" 2>/dev/null || true

if [ "$MODE" = "prod" ]; then
    # Productiemodus: bouw frontend en serveer via backend
    echo -e "${BLUE}Frontend bouwen...${NC}"
    cd "$FRONTEND_DIR"
    if [ ! -d "node_modules" ]; then
        npm install
    fi
    npm run build

    echo -e "\n${GREEN}✅ PrijsScanner is klaar!${NC}"
    echo -e "   Backend + Frontend: ${YELLOW}http://$(hostname -I | awk '{print $1}'):8000${NC}"
    echo -e "   Op iPhone (zelfde WiFi): open de bovenstaande URL in Safari"
    echo -e "   → Deel → 'Zet op beginscherm' voor PWA-installatie\n"

    cd "$BACKEND_DIR"
    uvicorn main:app --host 0.0.0.0 --port 8000

else
    # Devmodus: start backend en frontend devserver parallel
    echo -e "${BLUE}Node dependencies controleren...${NC}"
    cd "$FRONTEND_DIR"
    if [ ! -d "node_modules" ]; then
        npm install
    fi

    echo -e "\n${GREEN}✅ PrijsScanner devmodus starten...${NC}"
    echo -e "   Backend API:  ${YELLOW}http://localhost:8000/docs${NC}"
    echo -e "   Frontend:     ${YELLOW}http://localhost:5173${NC}\n"

    # Start backend op achtergrond
    cd "$BACKEND_DIR"
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
    BACKEND_PID=$!

    # Start frontend
    cd "$FRONTEND_DIR"
    npm run dev &
    FRONTEND_PID=$!

    # Wacht op Ctrl+C
    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo -e '\n${GREEN}PrijsScanner gestopt.${NC}'" INT TERM
    wait $BACKEND_PID $FRONTEND_PID
fi
