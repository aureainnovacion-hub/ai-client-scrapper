#!/usr/bin/env bash
# =============================================================================
# Script de Verificación de Salud del Entorno — ai-client-scrapper
# Aurea Innovación
# =============================================================================
set -euo pipefail

ERRORS=0
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=============================================="
echo "  Verificación de Salud del Entorno"
echo "=============================================="

# ── Archivo .env ──────────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo -e "${RED}ERROR: No se encontró el archivo .env${NC}"
    echo "       Ejecute: bash scripts/setup.sh"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}OK: Archivo .env encontrado.${NC}"
fi

# ── Variables críticas ────────────────────────────────────────
REQUIRED_VARS=("APP_NAME" "SEARCH_KEYWORD" "DATABASE_URL")
for var in "${REQUIRED_VARS[@]}"; do
    if grep -q "^${var}=.\+" .env 2>/dev/null; then
        echo -e "${GREEN}OK: Variable ${var} configurada.${NC}"
    else
        echo -e "${YELLOW}AVISO: La variable ${var} no está configurada en .env${NC}"
    fi
done

# ── Python y dependencias ─────────────────────────────────────
if command -v python3 &> /dev/null; then
    echo -e "${GREEN}OK: Python3 disponible ($(python3 --version)).${NC}"
else
    echo -e "${RED}ERROR: Python3 no encontrado.${NC}"
    ERRORS=$((ERRORS + 1))
fi

if python3 -c "import playwright" 2>/dev/null; then
    echo -e "${GREEN}OK: Playwright instalado.${NC}"
else
    echo -e "${YELLOW}AVISO: Playwright no instalado. Ejecute: pip3 install playwright && python3 -m playwright install chromium${NC}"
fi

if python3 -c "import sqlalchemy" 2>/dev/null; then
    echo -e "${GREEN}OK: SQLAlchemy instalado.${NC}"
else
    echo -e "${RED}ERROR: SQLAlchemy no instalado.${NC}"
    ERRORS=$((ERRORS + 1))
fi

# ── Docker ────────────────────────────────────────────────────
if command -v docker &> /dev/null; then
    echo -e "${GREEN}OK: Docker disponible ($(docker --version | cut -d' ' -f3 | tr -d ',')).${NC}"
else
    echo -e "${YELLOW}AVISO: Docker no encontrado. Necesario para 'make dev'.${NC}"
fi

# ── Directorios ───────────────────────────────────────────────
for dir in data logs; do
    if [ -d "$dir" ]; then
        echo -e "${GREEN}OK: Directorio $dir/ existe.${NC}"
    else
        echo -e "${YELLOW}AVISO: Directorio $dir/ no existe. Se creará al ejecutar el scraper.${NC}"
    fi
done

echo ""
if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}Se encontraron ${ERRORS} error(es). Corrija los problemas antes de continuar.${NC}"
    exit 1
else
    echo -e "${GREEN}Verificación completada sin errores críticos.${NC}"
fi
