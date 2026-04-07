"""
utils.py
--------
Utilidades compartidas: configuración de logging, limpieza de datos
y exportación a CSV.
"""

import logging
import os
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from models import Lead


# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────

def setup_logger(log_dir: str = "logs", level: int = logging.INFO) -> logging.Logger:
    """
    Configura un logger con salida a consola y archivo rotativo.

    Args:
        log_dir: Directorio donde se almacenan los archivos de log.
        level:   Nivel de logging (por defecto INFO).

    Returns:
        Logger configurado.
    """
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_path = os.path.join(log_dir, "scraper.log")

    logger = logging.getLogger("ai_client_scrapper")
    logger.setLevel(level)

    if logger.handlers:
        return logger  # Evitar handlers duplicados en re-ejecuciones

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler de consola
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Handler de archivo con rotación (5 MB, 3 backups)
    fh = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=3)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


# ─────────────────────────────────────────────
# Limpieza y normalización de datos
# ─────────────────────────────────────────────

def clean_text(text: Optional[str]) -> Optional[str]:
    """Elimina espacios redundantes y caracteres de control."""
    if not text:
        return None
    return re.sub(r"\s+", " ", text.strip()) or None


def extract_email(text: Optional[str]) -> Optional[str]:
    """Extrae el primer email encontrado en un texto."""
    if not text:
        return None
    match = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
    return match.group(0).lower() if match else None


def extract_nif(text: Optional[str]) -> Optional[str]:
    """
    Extrae un NIF/CIF español de un texto.
    Formatos soportados: A12345678 (CIF), 12345678Z (DNI), X1234567Z (NIE).
    """
    if not text:
        return None
    pattern = r"\b([A-HJ-NP-SUVW]\d{7}[0-9A-J]|\d{8}[A-Z]|[XYZ]\d{7}[A-Z])\b"
    match = re.search(pattern, text.upper())
    return match.group(0) if match else None


def normalize_url(url: Optional[str]) -> Optional[str]:
    """Asegura que la URL tenga esquema http/https."""
    if not url:
        return None
    url = url.strip()
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url or None


# ─────────────────────────────────────────────
# Persistencia y exportación
# ─────────────────────────────────────────────

def save_lead(session: Session, lead_data: dict, logger: logging.Logger) -> bool:
    """
    Inserta un lead en la base de datos si no existe ya (deduplicación por nombre+fuente).

    Args:
        session:   Sesión SQLAlchemy activa.
        lead_data: Diccionario con los campos del lead.
        logger:    Logger para registrar eventos.

    Returns:
        True si se insertó, False si ya existía o hubo error.
    """
    nombre = clean_text(lead_data.get("nombre"))
    fuente = lead_data.get("fuente", "desconocida")

    if not nombre:
        logger.warning("Lead descartado: nombre vacío.")
        return False

    existing = (
        session.query(Lead)
        .filter_by(nombre=nombre, fuente=fuente)
        .first()
    )
    if existing:
        logger.debug(f"Lead duplicado ignorado: '{nombre}' ({fuente})")
        return False

    lead = Lead(
        nombre=nombre,
        web=normalize_url(lead_data.get("web")),
        nif=extract_nif(lead_data.get("nif") or lead_data.get("nif_raw")),
        email=extract_email(lead_data.get("email") or lead_data.get("email_raw")),
        fuente=fuente,
        keyword=lead_data.get("keyword"),
    )
    session.add(lead)
    try:
        session.commit()
        logger.info(f"Lead guardado: '{nombre}' | web={lead.web} | email={lead.email}")
        return True
    except Exception as exc:
        session.rollback()
        logger.error(f"Error al guardar lead '{nombre}': {exc}")
        return False


def export_to_csv(session: Session, output_path: str, logger: logging.Logger) -> None:
    """
    Exporta todos los leads de la base de datos a un archivo CSV.

    Args:
        session:     Sesión SQLAlchemy activa.
        output_path: Ruta del archivo CSV de salida.
        logger:      Logger para registrar eventos.
    """
    leads = session.query(Lead).all()
    if not leads:
        logger.warning("No hay leads para exportar.")
        return

    data = [lead.to_dict() for lead in leads]
    df = pd.DataFrame(data)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    logger.info(f"Exportados {len(df)} leads a '{output_path}'.")
