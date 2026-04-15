"""
utils.py
--------
Utilidades compartidas: logging, limpieza de datos, extracción de NIF/CIF
con validación de algoritmo de control, búsqueda de NIF por nombre de empresa
en fuentes oficiales (OpenData Registradores / emprecif.com), y persistencia.
"""

import logging
import os
import re
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, List, Dict
from urllib.parse import urlparse

import requests
import pandas as pd
from sqlalchemy.orm import Session

from src.models import Lead


# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────

def setup_logger(log_dir: str = "logs", level: int = logging.INFO) -> logging.Logger:
    """Configura un logger con salida a consola y archivo rotativo."""
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
# Validación de Algoritmo de Control (NIF/CIF)
# ─────────────────────────────────────────────

def validate_spanish_id(id_str: str) -> bool:
    """
    Valida el formato y el dígito de control de un NIF/CIF/NIE español.
    Implementa el algoritmo oficial del Ministerio de Hacienda.
    """
    id_str = id_str.upper().replace("-", "").replace(".", "").replace(" ", "")
    if len(id_str) != 9:
        return False

    # NIE: Cambiar X, Y, Z por 0, 1, 2
    nie_prefix = {"X": "0", "Y": "1", "Z": "2"}
    if id_str[0] in nie_prefix:
        temp_id = nie_prefix[id_str[0]] + id_str[1:]
    else:
        temp_id = id_str

    # Patrón NIF (Persona física): 8 números + 1 letra
    if re.match(r"^\d{8}[A-Z]$", temp_id):
        letras = "TRWAGMYFPDXBNJZSQVHLCKE"
        return letras[int(temp_id[:8]) % 23] == temp_id[8]

    # Patrón CIF (Persona jurídica): 1 letra + 7 números + 1 control (letra o número)
    if re.match(r"^[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]$", id_str):
        letter = id_str[0]
        digits = [int(d) for d in id_str[1:8]]

        # Suma de posiciones pares (índice 1, 3, 5 → dígitos 2, 4, 6)
        even_sum = digits[1] + digits[3] + digits[5]

        # Suma de posiciones impares × 2 (con suma de dígitos si > 9)
        odd_sum = 0
        for i in [0, 2, 4, 6]:
            prod = digits[i] * 2
            odd_sum += (prod // 10) + (prod % 10)

        total_sum = even_sum + odd_sum
        control_digit = (10 - (total_sum % 10)) % 10
        control_letter = "JABCDEFGHI"[control_digit]

        last_char = id_str[8]
        if letter in "ABEH":      # Solo número
            return last_char == str(control_digit)
        elif letter in "PQSW":    # Solo letra
            return last_char == control_letter
        else:                      # Ambos válidos
            return last_char == str(control_digit) or last_char == control_letter

    return False


# ─────────────────────────────────────────────
# Extracción y Limpieza de Texto
# ─────────────────────────────────────────────

def clean_text(text: Optional[str]) -> Optional[str]:
    """Elimina espacios redundantes y caracteres de control."""
    if not text:
        return None
    return re.sub(r"\s+", " ", text.strip()) or None


def normalize_text_for_cif(text: str) -> str:
    """
    Normalización profunda del texto para facilitar la detección de CIFs.
    Elimina puntos dentro de números, colapsa espacios entre dígitos y
    elimina separadores entre letra-número propios del formato CIF.
    """
    text = text.upper().replace("\xa0", " ")
    # Eliminar puntos como separadores de miles dentro de números
    text = re.sub(r'(\d)\.(\d)', r'\1\2', text)
    # Colapsar espacios entre dígitos consecutivos
    text = re.sub(r'(\d)\s+(?=\d)', r'\1', text)
    # Eliminar separadores entre letra inicial y dígitos del CIF
    text = re.sub(r'([A-Z])\s*[-—·\.]\s*(\d)', r'\1\2', text)
    # Eliminar separadores entre dígitos y letra final del CIF
    text = re.sub(r'(\d)\s*[-—·\.]\s*([A-Z])', r'\1\2', text)
    return text


def extract_emails(text: Optional[str]) -> List[str]:
    """Extrae todos los emails únicos y válidos encontrados en un texto HTML/texto."""
    if not text:
        return []
    pattern = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    matches = re.findall(pattern, text)
    # Filtrar emails de imágenes, scripts, ejemplos y dominios de sistema
    blacklist = ['.png', '.jpg', '.gif', '.js', '.css', 'example.com',
                 'sentry.io', 'w3.org', 'schema.org', 'yourdomain']
    cleaned = [
        m.lower() for m in matches
        if not any(x in m.lower() for x in blacklist)
    ]
    return list(dict.fromkeys(cleaned))  # Preservar orden, eliminar duplicados


def extract_nifs(text: Optional[str]) -> List[str]:
    """
    Extrae NIFs/CIFs españoles únicos de un texto usando Regex y validación
    del algoritmo de control oficial.

    Prioriza los patrones con prefijo explícito (CIF:, NIF:) sobre los
    patrones genéricos para reducir falsos positivos.
    """
    if not text:
        return []

    text_norm = normalize_text_for_cif(text)

    # Patrones ordenados de mayor a menor especificidad
    patterns = [
        # Con prefijo explícito (máxima fiabilidad)
        r'(?:CIF|NIF|N\.I\.F\.|C\.I\.F\.|NIF/CIF|CIF/NIF)[:\s\-—·]*([A-Z0-9]{9})',
        # CIF de persona jurídica: letra + 7 dígitos + control
        r'\b([ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J])\b',
        # NIF de persona física: 8 dígitos + letra
        r'\b(\d{8}[A-Z])\b',
    ]

    found = []
    seen = set()
    for pattern in patterns:
        for m in re.findall(pattern, text_norm):
            cif_clean = re.sub(r'[^\w]', '', str(m).upper())
            if len(cif_clean) == 9 and cif_clean not in seen and validate_spanish_id(cif_clean):
                found.append(cif_clean)
                seen.add(cif_clean)

    return found


# ─────────────────────────────────────────────
# Búsqueda de NIF/CIF por nombre de empresa
# ─────────────────────────────────────────────

_EMPRECIF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
}


def lookup_nif_by_name(company_name: str, logger=None) -> Optional[str]:
    """
    Busca el NIF/CIF oficial de una empresa española por su nombre o razón
    social usando el buscador público de emprecif.com (datos del BORME).

    Estrategia:
    1. Limpiar el nombre de la empresa (eliminar formas jurídicas, puntuación).
    2. Consultar el buscador de emprecif.com con el nombre limpio.
    3. Extraer y validar el primer NIF/CIF encontrado en la respuesta.

    Retorna el NIF/CIF como string o None si no se encuentra.
    """
    if not company_name or len(company_name.strip()) < 3:
        return None

    # Limpiar el nombre: eliminar formas jurídicas y caracteres especiales
    name_clean = _clean_company_name(company_name)
    if not name_clean:
        return None

    try:
        # Búsqueda en emprecif.com (datos del BORME - fuente oficial)
        url = f"https://www.emprecif.com/empresas/buscar"
        params = {"q": name_clean}
        resp = requests.get(
            url,
            params=params,
            headers=_EMPRECIF_HEADERS,
            timeout=15,
            allow_redirects=True,
        )

        if resp.status_code != 200:
            if logger:
                logger.debug(f"emprecif.com devolvió HTTP {resp.status_code} para '{name_clean}'")
            return None

        # Extraer NIFs del HTML de respuesta
        nifs = extract_nifs(resp.text)
        if nifs:
            if logger:
                logger.debug(f"NIF encontrado en emprecif.com para '{name_clean}': {nifs[0]}")
            return nifs[0]

    except Exception as exc:
        if logger:
            logger.debug(f"Error en lookup_nif_by_name para '{company_name}': {exc}")

    return None


def _clean_company_name(name: str) -> str:
    """
    Limpia el nombre de empresa eliminando formas jurídicas, puntuación
    excesiva y palabras genéricas para mejorar la búsqueda.
    """
    # Formas jurídicas comunes en España
    legal_forms = [
        r'\bS\.?L\.?U?\.?\b', r'\bS\.?A\.?U?\.?\b', r'\bS\.?L\.?\b',
        r'\bS\.?A\.?\b', r'\bS\.?C\.?\b', r'\bS\.?L\.?L\.?\b',
        r'\bS\.?C\.?P\.?\b', r'\bS\.?R\.?L\.?\b', r'\bS\.?A\.?T\.?\b',
        r'\bS\.?A\.?S\.?\b', r'\bCB\.?\b', r'\bAIE\.?\b',
        r'\bSERVICIO TÉCNICO OFICIAL\b', r'\bSERVICIO OFICIAL\b',
    ]
    result = name.upper()
    for pattern in legal_forms:
        result = re.sub(pattern, '', result, flags=re.IGNORECASE)

    # Eliminar caracteres especiales y espacios múltiples
    result = re.sub(r'[^\w\s]', ' ', result)
    result = re.sub(r'\s+', ' ', result).strip()

    # Tomar solo las primeras 4 palabras significativas (evitar queries muy largas)
    words = [w for w in result.split() if len(w) > 2]
    return ' '.join(words[:4])


# ─────────────────────────────────────────────
# Normalización de URLs
# ─────────────────────────────────────────────

def normalize_url(url: Optional[str]) -> Optional[str]:
    """Asegura que la URL tenga esquema http/https y sea válida."""
    if not url:
        return None
    url = url.strip()
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    # Verificar que tenga al menos un dominio válido
    try:
        parsed = urlparse(url)
        if not parsed.netloc or '.' not in parsed.netloc:
            return None
    except Exception:
        return None
    return url


# ─────────────────────────────────────────────
# Persistencia
# ─────────────────────────────────────────────

def save_lead(session: Session, lead_data: dict, logger: logging.Logger) -> bool:
    """
    Inserta o actualiza un lead en la base de datos.

    La lógica de actualización siempre sobreescribe campos vacíos con nuevos
    valores, y también actualiza el NIF si el nuevo valor es diferente al
    existente (para corregir NIFs incorrectos de ejecuciones anteriores).
    """
    nombre = lead_data.get("nombre", "").strip()
    fuente = lead_data.get("fuente", "desconocida")
    web = normalize_url(lead_data.get("web"))
    nif = lead_data.get("nif")
    email = lead_data.get("email")

    if not nombre or not (web or nif or email):
        return False

    existing = session.query(Lead).filter_by(nombre=nombre, fuente=fuente).first()
    if existing:
        updated = False
        # Actualizar NIF: si no tenía o si el nuevo es diferente (corrección)
        if nif and existing.nif != nif:
            existing.nif = nif
            updated = True
        if not existing.email and email:
            existing.email = email
            updated = True
        if not existing.web and web:
            existing.web = web
            updated = True
        if updated:
            session.commit()
            logger.info(f"Lead actualizado: '{nombre}' | NIF={existing.nif} | Email={existing.email}")
        return False

    lead = Lead(
        nombre=nombre,
        web=web,
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
    """Exporta todos los leads a CSV con codificación UTF-8 BOM para Excel."""
    leads = session.query(Lead).all()
    if not leads:
        logger.warning("No hay leads para exportar.")
        return
    data = [lead.to_dict() for lead in leads]
    df = pd.DataFrame(data)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    logger.info(f"Exportados {len(df)} leads a '{output_path}'.")
