"""
scraper.py
----------
Script principal de scraping con navegación profunda para extraer NIF y Email.
"""

import os
import re
import sys
import time
import random
from pathlib import Path
from typing import Optional, List, Dict
from urllib.parse import urlparse, urlunparse, parse_qs

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeout

# Ajustar path para importar módulos locales
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import init_db
from src.utils import (
    setup_logger, save_lead, export_to_csv, clean_text, 
    extract_emails, extract_nifs, normalize_url
)

# ─────────────────────────────────────────────
# Configuración
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
# Helpers de Navegación Profunda
# ─────────────────────────────────────────────

def random_delay(min_s: float = 1.2, max_s: float = 3.0) -> None:
    time.sleep(random.uniform(min_s, max_s))


def deep_extract_from_website(page: Page, web_url: str) -> Dict[str, Optional[str]]:
    """
    Navega por la web de la empresa buscando NIF y Email en páginas legales y de contacto.
    """
    results = {"email": None, "nif": None}
    if not web_url or not web_url.startswith("http"):
        return results

    try:
        # 1. Visitar Home
        logger.debug(f"Visitando Home: {web_url}")
        page.goto(web_url, timeout=20_000, wait_until="domcontentloaded")
        random_delay(1, 2)
        html_home = page.content()
        
        emails = extract_emails(html_home)
        nifs = extract_nifs(html_home)
        
        if emails: results["email"] = emails[0]
        if nifs: results["nif"] = nifs[0]

        # Si ya tenemos ambos, terminamos
        if results["email"] and results["nif"]:
            return results

        # 2. Buscar enlaces a páginas legales o contacto
        # Selectores comunes para Aviso Legal, Privacidad y Contacto
        legal_links = page.evaluate("""
            () => {
                const keywords = ['aviso legal', 'legal notice', 'privacidad', 'privacy', 'contacto', 'contact', 'cookies'];
                const links = Array.from(document.querySelectorAll('a'));
                return links
                    .filter(a => keywords.some(k => a.innerText.toLowerCase().includes(k)))
                    .map(a => a.href)
                    .filter(href => href.startsWith('http'));
            }
        """)
        
        # Limitar a las 3 páginas más prometedoras para no tardar demasiado
        target_links = list(set(legal_links))[:3]
        
        for link in target_links:
            if results["email"] and results["nif"]:
                break
            try:
                logger.debug(f"Navegación profunda a: {link}")
                page.goto(link, timeout=15_000, wait_until="domcontentloaded")
                random_delay(0.5, 1.5)
                html_page = page.content()
                
                new_emails = extract_emails(html_page)
                new_nifs = extract_nifs(html_page)
                
                if not results["email"] and new_emails: results["email"] = new_emails[0]
                if not results["nif"] and new_nifs: results["nif"] = new_nifs[0]
            except Exception:
                continue

    except Exception as exc:
        logger.debug(f"Error en navegación profunda '{web_url}': {exc}")
    
    return results


# ─────────────────────────────────────────────
# Scrapers por Fuente
# ─────────────────────────────────────────────

def scrape_paginas_amarillas(page: Page, session, keyword: str, max_pages: int) -> int:
    source = "Páginas Amarillas"
    keyword_slug = keyword.replace(" ", "-").lower()
    raw_leads = []

    for page_num in range(1, max_pages + 1):
        url = f"https://www.paginasamarillas.es/search/{keyword_slug}/all-ma/all-pr/all-is/all-ci/all-ba/all-pu/all-nc/{page_num}?what={keyword.replace(' ', '+')}&qc=true"
        logger.info(f"[{source}] Listado página {page_num}")

        try:
            page.goto(url, timeout=30_000, wait_until="domcontentloaded")
            random_delay(2, 4)
            page.wait_for_selector("div.listado-item", timeout=10_000)
            
            cards = page.evaluate("""
                () => {
                    return Array.from(document.querySelectorAll('div.listado-item')).map(card => {
                        const h2 = card.querySelector('h2');
                        const webEl = card.querySelector('a.web');
                        return {
                            nombre: h2 ? h2.innerText.replace('+info','').trim() : '',
                            web: webEl ? webEl.href : ''
                        };
                    }).filter(d => d.nombre.length > 0);
                }
            """)
            raw_leads.extend(cards)
            
            if not page.query_selector('a[rel="next"]'):
                break
        except Exception as e:
            logger.warning(f"[{source}] Error en página {page_num}: {e}")
            break

    total_saved = 0
    for data in raw_leads:
        web_url = normalize_url(data.get("web"))
        deep_data = {"email": None, "nif": None}
        
        if web_url:
            deep_data = deep_extract_from_website(page, web_url)
        
        lead_final = {
            "nombre": data["nombre"],
            "web": web_url,
            "email": deep_data["email"],
            "nif": deep_data["nif"],
            "fuente": source,
            "keyword": keyword
        }
        
        if save_lead(session, lead_final, logger):
            total_saved += 1
            
    return total_saved


def run_all_scrapers():
    logger.info("="*60)
    logger.info(f"INICIANDO SCRAPER PROFUNDO - KEYWORD: {KEYWORD}")
    logger.info("="*60)
    
    session = init_db(DATABASE_URL)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
        page = context.new_page()
        
        try:
            # Por brevedad en esta actualización, nos centramos en la fuente principal
            # pero la lógica de deep_extract_from_website es aplicable a todas.
            count = scrape_paginas_amarillas(page, session, KEYWORD, MAX_PAGES)
            logger.info(f"Proceso finalizado. Total leads nuevos con NIF/Email: {count}")
        finally:
            browser.close()
    
    export_to_csv(session, str(PROJECT_ROOT / "data" / "leads.csv"), logger)
    session.close()

if __name__ == "__main__":
    run_all_scrapers()
