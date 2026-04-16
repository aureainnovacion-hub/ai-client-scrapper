# ==============================================================
# Makefile — ai-client-scrapper
# Aurea Innovación
# Centraliza todos los comandos del proyecto.
# Uso: make <comando>
# ==============================================================

ifneq (,$(wildcard ./.env))
    include .env
    export
endif

APP_NAME     ?= ai-client-scrapper
PYTHON       ?= python3
PIP          ?= pip3
SCRAPER_DIR  := apps/scraper
TESTS_DIR    := tests

# Colores
CYAN  = \033[0;36m
GREEN = \033[0;32m
RED   = \033[0;31m
NC    = \033[0m

.PHONY: help install dev up down logs test test-unit test-e2e \
        build clean scrape enrich db-migrate db-seed lint format

# ── Ayuda ─────────────────────────────────────────────────────
help:
	@echo "$(CYAN)============================================================$(NC)"
	@echo "$(CYAN)  $(APP_NAME) — Comandos Disponibles$(NC)"
	@echo "$(CYAN)============================================================$(NC)"
	@echo "$(GREEN)make install$(NC)      - Instala dependencias y configura el entorno"
	@echo "$(GREEN)make dev$(NC)          - Inicia el entorno de desarrollo completo (Docker)"
	@echo "$(GREEN)make up$(NC)           - Levanta los contenedores en segundo plano"
	@echo "$(GREEN)make down$(NC)         - Detiene y elimina los contenedores"
	@echo "$(GREEN)make logs$(NC)         - Muestra los logs de todos los servicios"
	@echo "$(GREEN)make scrape$(NC)       - Ejecuta el scraper manualmente"
	@echo "$(GREEN)make enrich$(NC)       - Ejecuta el enriquecimiento BDNS manualmente"
	@echo "$(GREEN)make test$(NC)         - Ejecuta todas las pruebas"
	@echo "$(GREEN)make test-unit$(NC)    - Ejecuta solo las pruebas unitarias"
	@echo "$(GREEN)make test-e2e$(NC)     - Ejecuta las pruebas end-to-end"
	@echo "$(GREEN)make build$(NC)        - Construye las imágenes de producción"
	@echo "$(GREEN)make clean$(NC)        - Limpia volúmenes, caché y archivos temporales"
	@echo "$(GREEN)make lint$(NC)         - Ejecuta el linter (flake8)"
	@echo "$(GREEN)make format$(NC)       - Formatea el código (black + isort)"
	@echo "$(GREEN)make db-migrate$(NC)   - Ejecuta las migraciones de base de datos"

# ── Configuración e Instalación ───────────────────────────────
install:
	@echo "$(GREEN)>> Configurando entorno inicial...$(NC)"
	@chmod +x scripts/setup.sh
	@./scripts/setup.sh
	@echo "$(GREEN)>> Instalando dependencias Python...$(NC)"
	@$(PIP) install -r $(SCRAPER_DIR)/requirements.txt
	@$(PYTHON) -m playwright install chromium
	@echo "$(GREEN)>> Instalación completada.$(NC)"

# ── Docker Compose ────────────────────────────────────────────
dev:
	@echo "$(GREEN)>> Iniciando entorno de desarrollo...$(NC)"
	@docker compose up --build

up:
	@echo "$(GREEN)>> Levantando servicios en segundo plano...$(NC)"
	@docker compose up -d

down:
	@echo "$(GREEN)>> Deteniendo servicios...$(NC)"
	@docker compose down

logs:
	@docker compose logs -f

build:
	@echo "$(GREEN)>> Construyendo imágenes de producción...$(NC)"
	@docker compose build --build-arg TARGET=production

clean:
	@echo "$(RED)>> Limpiando entorno (borra BD local y caché)...$(NC)"
	@docker compose down -v --remove-orphans
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf .pytest_cache

# ── Pipeline Manual ───────────────────────────────────────────
scrape:
	@echo "$(GREEN)>> Ejecutando scraper...$(NC)"
	@$(PYTHON) $(SCRAPER_DIR)/src/controllers/scraper.py

enrich:
	@echo "$(GREEN)>> Ejecutando enriquecimiento BDNS...$(NC)"
	@$(PYTHON) $(SCRAPER_DIR)/src/controllers/enrich_leads.py

pipeline:
	@echo "$(GREEN)>> Ejecutando pipeline completo...$(NC)"
	@$(PYTHON) $(SCRAPER_DIR)/run_pipeline.py

# ── Pruebas ───────────────────────────────────────────────────
test:
	@echo "$(GREEN)>> Ejecutando todas las pruebas...$(NC)"
	@$(PYTHON) -m pytest $(TESTS_DIR)/ -v --tb=short

test-unit:
	@echo "$(GREEN)>> Ejecutando pruebas unitarias...$(NC)"
	@$(PYTHON) -m pytest $(TESTS_DIR)/unit/ -v --tb=short

test-e2e:
	@echo "$(GREEN)>> Ejecutando pruebas end-to-end...$(NC)"
	@$(PYTHON) -m pytest $(TESTS_DIR)/e2e/ -v --tb=short -s

test-integration:
	@echo "$(GREEN)>> Ejecutando pruebas de integración...$(NC)"
	@$(PYTHON) -m pytest $(TESTS_DIR)/integration/ -v --tb=short

# ── Calidad de Código ─────────────────────────────────────────
lint:
	@echo "$(GREEN)>> Ejecutando linter...$(NC)"
	@$(PYTHON) -m flake8 apps/ tests/ --max-line-length=120 --exclude=__pycache__

format:
	@echo "$(GREEN)>> Formateando código...$(NC)"
	@$(PYTHON) -m black apps/ tests/ --line-length=120
	@$(PYTHON) -m isort apps/ tests/

# ── Base de Datos ─────────────────────────────────────────────
db-migrate:
	@echo "$(GREEN)>> Ejecutando migraciones...$(NC)"
	@echo "SQLite: las tablas se crean automáticamente al iniciar el scraper."
	@echo "Para PostgreSQL, ejecutar los scripts en apps/database/migrations/"

db-seed:
	@echo "$(GREEN)>> Poblando base de datos con datos de prueba...$(NC)"
	@echo "Ejecutando scripts desde apps/database/seeds/"

# ── Health Check ──────────────────────────────────────────────
health:
	@echo "$(GREEN)>> Verificando salud del entorno...$(NC)"
	@chmod +x scripts/health-check.sh
	@./scripts/health-check.sh
