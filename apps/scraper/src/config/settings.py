"""
settings.py
-----------
Configuración centralizada del módulo scraper.
Todas las variables de entorno se leen desde aquí.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Raíz del proyecto (5 niveles arriba desde config/)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ── Scraper ───────────────────────────────────────────────────────────────────
SEARCH_KEYWORD: str = os.getenv("SEARCH_KEYWORD", "instalaciones solares")
MAX_PAGES: int = int(os.getenv("MAX_PAGES", "5"))
HEADLESS: bool = os.getenv("HEADLESS", "true").lower() != "false"

# ── Base de datos ─────────────────────────────────────────────────────────────
_raw_db = os.getenv("DATABASE_URL", "sqlite:///data/leads.db")
if _raw_db.startswith("sqlite:///") and not _raw_db.replace("sqlite:///", "").startswith("/"):
    DATABASE_URL: str = f"sqlite:///{PROJECT_ROOT / _raw_db.replace('sqlite:///', '')}"
else:
    DATABASE_URL: str = _raw_db

# ── Logging ───────────────────────────────────────────────────────────────────
_raw_log = os.getenv("LOG_DIR", "logs")
LOG_DIR: str = str(PROJECT_ROOT / _raw_log) if not Path(_raw_log).is_absolute() else _raw_log

# ── Enriquecimiento BDNS ──────────────────────────────────────────────────────
PRIORITY_MIN_AMOUNT: float = float(os.getenv("PRIORITY_MIN_AMOUNT", "10000"))
PRIORITY_MIN_COUNT: int = int(os.getenv("PRIORITY_MIN_COUNT", "2"))

# ── SMTP ──────────────────────────────────────────────────────────────────────
SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: str = os.getenv("SMTP_USER", "")
SMTP_PASS: str = os.getenv("SMTP_PASS", "")
DRY_RUN: bool = os.getenv("DRY_RUN", "true").lower() != "false"

# ── Rutas de datos ────────────────────────────────────────────────────────────
DATA_DIR: Path = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
