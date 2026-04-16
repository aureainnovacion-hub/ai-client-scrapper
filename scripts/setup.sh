#!/usr/bin/env bash
# =============================================================================
# Script de Configuración Inicial — ai-client-scrapper
# Aurea Innovación
# Ejecutar una sola vez al clonar el repositorio: bash scripts/setup.sh
# =============================================================================
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "=============================================="
echo "  Configuración Inicial — ai-client-scrapper"
echo "=============================================="

# ── 1. Crear archivo .env ─────────────────────────────────────
if [ ! -f "config/envs/example.env" ]; then
    echo -e "${RED}ERROR: No se encontró config/envs/example.env${NC}"
    exit 1
fi

if [ ! -f ".env" ]; then
    echo -e "${GREEN}Creando archivo .env a partir de example.env...${NC}"
    cp config/envs/example.env .env
    echo -e "${YELLOW}AVISO: Se ha creado el archivo .env. Complete los valores antes de ejecutar.${NC}"
else
    echo -e "${GREEN}El archivo .env ya existe. No se sobreescribirá.${NC}"
fi

# ── 2. Crear directorios de datos y logs ─────────────────────
mkdir -p data logs
echo -e "${GREEN}Directorios data/ y logs/ listos.${NC}"

# ── 3. Instalar dependencias Python ──────────────────────────
if command -v pip3 &> /dev/null; then
    echo -e "${GREEN}Instalando dependencias Python...${NC}"
    pip3 install -r apps/scraper/requirements.txt --quiet
    echo -e "${GREEN}Instalando navegador Chromium para Playwright...${NC}"
    python3 -m playwright install chromium
else
    echo -e "${YELLOW}AVISO: pip3 no encontrado. Instala las dependencias manualmente:${NC}"
    echo "  pip3 install -r apps/scraper/requirements.txt"
    echo "  python3 -m playwright install chromium"
fi

# ── 4. Instalar hooks de pre-commit ──────────────────────────
if command -v pre-commit &> /dev/null; then
    echo -e "${GREEN}Instalando hooks de pre-commit...${NC}"
    pre-commit install
    pre-commit install --hook-type commit-msg
else
    echo -e "${YELLOW}AVISO: pre-commit no instalado. Recomendado: pip3 install pre-commit${NC}"
fi

echo ""
echo -e "${GREEN}=============================================="
echo "  Configuración completada."
echo "  Próximos pasos:"
echo "  1. Edita el archivo .env con tus valores reales."
echo "  2. Ejecuta: make dev  (Docker) o  make pipeline  (local)"
echo -e "==============================================${NC}"
