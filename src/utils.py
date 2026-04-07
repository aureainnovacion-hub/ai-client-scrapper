"""
utils.py
--------
Utilidades compartidas: configuración de logging, limpieza de datos,
extracción avanzada con Regex y exportación a CSV.
"""

import logging
import os
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, List

import pandas as pd
from sqlalchemy.orm import Session

from src.models import Lead


# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────

def setup_logger(log_dir: str = "logs", level: int = logging.INFO) -> logging.Logger:
    """
    Configura un logger con salida a consola y archivo rotativo.
    """
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_path = os.path.join(log_dir, "scraper.log")

    logger = logging.getLogger("ai_client_scrapper")
    logger.setLevel(level)

    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    fh = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=3)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


# ─────────────────────────────────────────────
# Extracción y Limpieza Avanzada
# ─────────────────────────────────────────────

def clean_text(text: Optional[str]) -> Optional[str]:
    """Elimina espacios redundantes y caracteres de control."""
    if not text:
        return None
    return re.sub(r"\s+", " ", text.strip()) or None


def extract_emails(text: Optional[str]) -> List[str]:
    """Extrae todos los emails únicos encontrados en un texto."""
    if not text:
        return []
    pattern = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    matches = re.findall(pattern, text)
    return list(set(m.lower() for m in matches))


def extract_nifs(text: Optional[str]) -> List[str]:
    """
    Extrae NIFs/CIFs españoles únicos de un texto usando Regex robusto.
    Formatos: A12345678, B-12345678, 12345678-Z, etc.
    """
    if not text:
        return []
    
    # Normalizar texto: quitar guiones y puntos que suelen separar el NIF
    text_clean = text.upper().replace("-", "").replace(".", "").replace(" ", "")
    
    # Patrón NIF/CIF: Letra + 8 dígitos O 8 dígitos + Letra
    # [A-H|J|N-P|S-U|V|W] para CIFs de empresas
    pattern = r"([A-HJ-NP-SUVW]\d{7}[0-9A-J]|\d{8}[A-Z]|[XYZ]\d{7}[A-Z])"
    matches = re.findall(pattern, text_clean)
    
    return list(set(matches))


def normalize_nif(nif: Optional[str]) -> Optional[str]:
    """Limpia el NIF de espacios, guiones y puntos."""
    if not nif:
        return None
    return nif.upper().replace("-", "").replace(".", "").replace(" ", "").strip()


def normalize_url(url: Optional[str]) -> Optional[str]:
    """Asegura que la URL tenga esquema http/https."""
    if not url:
        return None
    url = url.strip()
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url or None


# ─────────────────────────────────────────────
# Persistencia y Exportación
# ─────────────────────────────────────────────

def save_lead(session: Session, lead_data: dict, logger: logging.Logger) -> bool:
    """
    Inserta un lead en la base de datos con filtros estrictos.
    REGLA: Solo se guarda si tiene NIF o Email.
    """
    nombre = clean_text(lead_data.get("nombre"))
    fuente = lead_data.get("fuente", "desconocida")
    
    # Extraer y normalizar datos
    nif_raw = lead_data.get("nif") or lead_data.get("nif_raw")
    email_raw = lead_data.get("email") or lead_data.get("email_raw")
    
    nifs = extract_nifs(nif_raw) if nif_raw else []
    emails = extract_emails(email_raw) if email_raw else []
    
    nif = normalize_nif(nifs[0]) if nifs else None
    email = emails[0] if emails else None

    # FILTRO OBLIGATORIO: NIF o Email
    if not nif and not email:
        logger.warning(f"Lead descartado (Sin NIF ni Email): '{nombre}'")
        return False

    if not nombre:
        logger.warning("Lead descartado: nombre vacío.")
        return False

    # Deduplicación
    existing = session.query(Lead).filter_by(nombre=nombre, fuente=fuente).first()
    if existing:
        # Actualizar si el nuevo tiene más info
        updated = False
        if not existing.nif and nif:
            existing.nif = nif
            updated = True
        if not existing.email and email:
            existing.email = email
            updated = True
        
        if updated:
            session.commit()
            logger.info(f"Lead actualizado: '{nombre}'")
        return False

    lead = Lead(
        nombre=nombre,
        web=normalize_url(lead_data.get("web")),
        nif=nif,
        email=email,
        fuente=fuente,
        keyword=lead_data.get("keyword"),
    )
    session.add(lead)
    try:
        session.commit()
        logger.info(f"Lead guardado: '{nombre}' | NIF={nif} | Email={email}")
        return True
    except Exception as exc:
        session.rollback()
        logger.error(f"Error al guardar lead '{nombre}': {exc}")
        return False


def export_to_csv(session: Session, output_path: str, logger: logging.Logger) -> None:
    """Exporta todos los leads a CSV."""
    leads = session.query(Lead).all()
    if not leads:
        logger.warning("No hay leads para exportar.")
        return

    data = [lead.to_dict() for lead in leads]
    df = pd.DataFrame(data)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    logger.info(f"Exportados {len(df)} leads a '{output_path}'.")
