"""
scraper.py
----------
Script principal de scraping con navegación profunda, prioridad a páginas
legales para extracción de NIF/CIF y enriquecimiento desde fuentes oficiales.

Flujo por empresa:
  1. Obtener nombre y URL web desde Páginas Amarillas.
  2. Navegar la web de la empresa: Home → Aviso Legal → Contacto.
  3. Si no se encontró NIF en la web, buscar por nombre en emprecif.com (BORME).
  4. Guardar el lead en la base de datos.
"""

import os
import re
import sys
import time
import random
from pathlib import Path
from typing import Optional, List, Dict

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout

# Ajustar path al raíz del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import init_db
from src.utils import (
    setup_logger, save_lead, export_to_csv, clean_text,
    extract_emails, extract_nifs, normalize_url, validate_spanish_id,
    lookup_nif_by_name,
)

# ─────────────────────────────────────────────
# Configuración desde variables de entorno
# ─────────────────────────────────────────────

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

KEYWORD = os.getenv("SEARCH_KEYWORD", "instalaciones solares")
MAX_PAGES = int(os.getenv("MAX_PAGES", "5"))
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/leads.db")
LOG_DIR = os.getenv("LOG_DIR", "logs")
HEADLESS = os.getenv("HEADLESS", "true").lower() != "false"

PROJECT_ROOT = Path(__file__).parent.parent
db_path_raw = DATABASE_URL.replace("sqlite:///", "")
if not Path(db_path_raw).is_absolute():
    DATABASE_URL = f"sqlite:///{PROJECT_ROOT / db_path_raw}"
LOG_DIR = str(PROJECT_ROOT / LOG_DIR)

logger = setup_logger(LOG_DIR)


# ─────────────────────────────────────────────
# Palabras clave para navegación interna
# ─────────────────────────────────────────────

# Páginas con alta probabilidad de contener el CIF oficial
LEGAL_KEYWORDS = [
    "aviso legal", "legal notice", "aviso-legal", "avisolegal",
    "privacidad", "privacy", "politica-privacidad", "politica privacidad",
    "rgpd", "lopd", "proteccion de datos", "protección de datos",
    "quienes somos", "quiénes somos", "sobre nosotros", "about us",
    "informacion legal", "información legal",
]

# Páginas con alta probabilidad de contener el email de contacto
CONTACT_KEYWORDS = [
    "contacto", "contact", "contactar", "contactenos", "contáctenos",
    "contactenos", "escribenos", "escríbenos",
]


def random_delay(min_s: float = 0.8, max_s: float = 2.0) -> None:
    """Pausa aleatoria para simular comportamiento humano y evitar bloqueos."""
    time.sleep(random.uniform(min_s, max_s))


# ─────────────────────────────────────────────
# Extracción profunda desde la web de la empresa
# ─────────────────────────────────────────────

def deep_extract_from_website(page: Page, web_url: str) -> Dict[str, Optional[str]]:
    """
    Navega la web de la empresa buscando NIF/CIF y email con prioridad absoluta
    a las páginas de Aviso Legal (donde el CIF es obligatorio por ley).

    Estrategia de prioridad:
      1. Página Home (extracción inicial)
      2. Páginas de Aviso Legal / Privacidad (máxima fiabilidad para CIF)
      3. Páginas de Contacto (para email)

    Retorna dict con claves 'email' y 'nif' (ambas pueden ser None).
    """
    results = {"email": None, "nif": None}

    if not web_url or not web_url.startswith("http"):
        return results

    try:
        # ── 1. Visitar la página Home ──────────────────────────────────────
        logger.debug(f"[DeepScrape] Home: {web_url}")
        page.goto(web_url, timeout=20_000, wait_until="domcontentloaded")
        random_delay(0.5, 1.0)
        html_home = page.content()

        emails_home = extract_emails(html_home)
        nifs_home = extract_nifs(html_home)

        if emails_home:
            results["email"] = emails_home[0]
        if nifs_home:
            results["nif"] = nifs_home[0]

        # ── 2. Recopilar todos los enlaces internos ────────────────────────
        try:
            all_links = page.evaluate("""
                () => {
                    const base = window.location.origin;
                    const links = Array.from(document.querySelectorAll('a[href]'));
                    return links.map(a => ({
                        text: (a.innerText || a.title || a.getAttribute('aria-label') || '').toLowerCase().trim(),
                        href: a.href
                    })).filter(l =>
                        l.href &&
                        (l.href.startsWith('http') || l.href.startsWith('/')) &&
                        !l.href.includes('#') &&
                        !l.href.match(/\\.(pdf|jpg|png|gif|zip|doc|xls)$/i)
                    );
                }
            """)
        except Exception:
            all_links = []

        # Clasificar enlaces por tipo
        legal_links = []
        contact_links = []
        base_domain = _get_domain(web_url)

        for link in all_links:
            href = link.get('href', '')
            text = link.get('text', '')
            # Solo enlaces del mismo dominio
            if base_domain and base_domain not in href and not href.startswith('/'):
                continue
            if any(k in text for k in LEGAL_KEYWORDS) or any(k in href.lower() for k in LEGAL_KEYWORDS):
                legal_links.append(href)
            elif any(k in text for k in CONTACT_KEYWORDS) or any(k in href.lower() for k in CONTACT_KEYWORDS):
                contact_links.append(href)

        # ── 3. Prioridad 1: Aviso Legal (CIF obligatorio por LSSI) ─────────
        visited_legal = set()
        for link in legal_links[:3]:  # Máximo 3 páginas legales
            if link in visited_legal:
                continue
            visited_legal.add(link)
            try:
                logger.debug(f"[DeepScrape] Legal: {link}")
                page.goto(link, timeout=15_000, wait_until="domcontentloaded")
                random_delay(0.5, 1.0)
                html_legal = page.content()

                nifs_legal = extract_nifs(html_legal)
                emails_legal = extract_emails(html_legal)

                # El CIF del Aviso Legal es el más fiable → siempre sobreescribir
                if nifs_legal:
                    results["nif"] = nifs_legal[0]
                    logger.debug(f"[DeepScrape] NIF en Aviso Legal: {results['nif']}")
                if emails_legal and not results["email"]:
                    results["email"] = emails_legal[0]

                # Si ya tenemos NIF del aviso legal, no seguimos buscando
                if results["nif"]:
                    break

            except PWTimeout:
                logger.debug(f"[DeepScrape] Timeout en página legal: {link}")
            except Exception as exc:
                logger.debug(f"[DeepScrape] Error en página legal '{link}': {exc}")

        # ── 4. Prioridad 2: Contacto (para email) ─────────────────────────
        if not results["email"]:
            for link in contact_links[:2]:
                try:
                    logger.debug(f"[DeepScrape] Contacto: {link}")
                    page.goto(link, timeout=15_000, wait_until="domcontentloaded")
                    random_delay(0.5, 1.0)
                    html_contact = page.content()
                    emails_contact = extract_emails(html_contact)
                    if emails_contact:
                        results["email"] = emails_contact[0]
                        # Aprovechar para buscar NIF también si aún no lo tenemos
                        if not results["nif"]:
                            nifs_contact = extract_nifs(html_contact)
                            if nifs_contact:
                                results["nif"] = nifs_contact[0]
                        break
                except Exception as exc:
                    logger.debug(f"[DeepScrape] Error en contacto '{link}': {exc}")

    except PWTimeout:
        logger.debug(f"[DeepScrape] Timeout al cargar home: {web_url}")
    except Exception as exc:
        logger.debug(f"[DeepScrape] Error en '{web_url}': {exc}")

    return results


def _get_domain(url: str) -> str:
    """Extrae el dominio base de una URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "")
    except Exception:
        return ""


# ─────────────────────────────────────────────
# Scraper de Páginas Amarillas
# ─────────────────────────────────────────────

def scrape_paginas_amarillas(page: Page, session, keyword: str, max_pages: int) -> int:
    """
    Extrae empresas de Páginas Amarillas para una keyword dada.

    Para cada empresa encontrada:
      1. Navega la web corporativa para extraer NIF y email.
      2. Si no se encontró NIF en la web, lo busca por nombre en emprecif.com.
      3. Guarda el lead en la base de datos.
    """
    source = "Páginas Amarillas"
    keyword_slug = keyword.replace(" ", "-").lower()
    raw_leads = []

    # ── Fase 1: Recopilar listado de empresas ─────────────────────────────
    for page_num in range(1, max_pages + 1):
        url = (
            f"https://www.paginasamarillas.es/search/{keyword_slug}/"
            f"all-ma/all-pr/all-is/all-ci/all-ba/all-pu/all-nc/{page_num}"
            f"?what={keyword.replace(' ', '+')}&qc=true"
        )
        logger.info(f"[{source}] Scraping listado página {page_num}: {url}")

        try:
            page.goto(url, timeout=30_000, wait_until="domcontentloaded")
            random_delay(1.5, 2.5)

            # Esperar a que carguen las tarjetas de empresa
            card_selector = "div.listado-item, article.advert-item, div[id^='advert-']"
            try:
                page.wait_for_selector(card_selector, timeout=12_000)
            except PWTimeout:
                logger.warning(f"[{source}] No se encontraron tarjetas en página {page_num}")
                break

            cards = page.evaluate("""
                () => {
                    const items = document.querySelectorAll(
                        'div.listado-item, article.advert-item, div[id^="advert-"]'
                    );
                    return Array.from(items).map(card => {
                        // Nombre de la empresa
                        const h2 = card.querySelector(
                            'h2, .business-name, a[title], [class*="name"]'
                        );
                        const nombre = h2
                            ? h2.innerText.replace('+info','').replace('Ver más','').trim()
                            : '';

                        // URL web corporativa (excluir links de paginasamarillas)
                        const webEl = card.querySelector(
                            'a.web, a[data-omniclick="web"], a[href*="http"]:not([href*="paginasamarillas"])'
                        );
                        const web = webEl ? webEl.href : '';

                        // Teléfono (opcional, para futuro uso)
                        const telEl = card.querySelector('[class*="phone"], [class*="tel"]');
                        const telefono = telEl ? telEl.innerText.trim() : '';

                        return { nombre, web, telefono };
                    }).filter(d => d.nombre && d.nombre.length > 2);
                }
            """)

            if cards:
                raw_leads.extend(cards)
                logger.info(f"[{source}] Página {page_num}: {len(cards)} empresas encontradas")
            else:
                logger.warning(f"[{source}] Página {page_num}: 0 empresas encontradas")
                break

            # Comprobar si hay página siguiente
            has_next = page.query_selector('a[rel="next"], .pagination-next, a.next')
            if not has_next:
                logger.info(f"[{source}] No hay más páginas de resultados.")
                break

        except PWTimeout:
            logger.warning(f"[{source}] Timeout en página {page_num}")
            break
        except Exception as exc:
            logger.warning(f"[{source}] Error en página {page_num}: {exc}")
            break

    if not raw_leads:
        logger.warning(f"[{source}] No se encontraron empresas para '{keyword}'")
        return 0

    # Deduplicar por nombre
    unique_leads = list({d['nombre']: d for d in raw_leads}.values())
    logger.info(f"[{source}] Total empresas únicas a procesar: {len(unique_leads)}")

    # ── Fase 2: Enriquecer cada empresa con NIF y email ───────────────────
    total_saved = 0

    for i, data in enumerate(unique_leads, 1):
        nombre = data["nombre"]
        web_url = normalize_url(data.get("web"))

        logger.info(f"[{source}] [{i}/{len(unique_leads)}] Procesando: '{nombre}' | Web: {web_url}")

        # Paso 2a: Extracción profunda desde la web corporativa
        deep_data = {"email": None, "nif": None}
        if web_url:
            deep_data = deep_extract_from_website(page, web_url)
            logger.debug(
                f"[{source}] Web scraping → NIF={deep_data['nif']} | Email={deep_data['email']}"
            )

        # Paso 2b: Si no se encontró NIF en la web, buscar por nombre en BORME
        nif_final = deep_data.get("nif")
        if not nif_final:
            logger.debug(f"[{source}] NIF no encontrado en web, buscando por nombre en BORME...")
            nif_borme = lookup_nif_by_name(nombre, logger)
            if nif_borme:
                nif_final = nif_borme
                logger.info(f"[{source}] NIF encontrado en BORME para '{nombre}': {nif_final}")

        lead_final = {
            "nombre": nombre,
            "web": web_url,
            "email": deep_data.get("email"),
            "nif": nif_final,
            "fuente": source,
            "keyword": keyword,
        }

        if save_lead(session, lead_final, logger):
            total_saved += 1

        # Pausa entre empresas para no sobrecargar los servidores
        random_delay(0.5, 1.5)

    return total_saved


# ─────────────────────────────────────────────
# Orquestador principal
# ─────────────────────────────────────────────

def run_all_scrapers():
    """Ejecuta todos los scrapers y exporta los resultados a CSV."""
    logger.info("=" * 60)
    logger.info(f"INICIANDO SCRAPER — KEYWORD: '{KEYWORD}' | MAX_PAGES: {MAX_PAGES}")
    logger.info("=" * 60)

    session = init_db(DATABASE_URL)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="es-ES",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        try:
            count = scrape_paginas_amarillas(page, session, KEYWORD, MAX_PAGES)
            logger.info(f"Proceso finalizado. Leads guardados/actualizados: {count}")
        except Exception as exc:
            logger.error(f"Error crítico en el scraper: {exc}")
        finally:
            browser.close()

    export_to_csv(session, str(PROJECT_ROOT / "data" / "leads.csv"), logger)
    session.close()
    logger.info("=" * 60)
    logger.info("SCRAPER FINALIZADO")
    logger.info("=" * 60)


if __name__ == "__main__":
    run_all_scrapers()
