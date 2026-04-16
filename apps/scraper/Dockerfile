# ==============================================================
# Dockerfile — apps/scraper
# Multi-stage build: dev (con herramientas de debug) y production
# ==============================================================

# ── Etapa base ────────────────────────────────────────────────
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# Dependencias de sistema para Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg libglib2.0-0 libnss3 libnspr4 libatk1.0-0 \
    libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxext6 libxfixes3 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install chromium

# ── Etapa de desarrollo ───────────────────────────────────────
FROM base AS dev

RUN pip install --no-cache-dir pytest pytest-cov

COPY . .
RUN mkdir -p /app/data /app/logs

CMD ["python", "run_pipeline.py"]

# ── Etapa de producción ───────────────────────────────────────
FROM base AS production

COPY . .
RUN mkdir -p /app/data /app/logs

EXPOSE 8501
CMD ["streamlit", "run", "src/pages/app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]
