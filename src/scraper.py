"""
scraper.py
----------
Script principal de scraping de empresas de instalaciones solares en España.

Fuentes:
  1. Páginas Amarillas (paginasamarillas.es) — selectores validados en producción
  2. Empresite / El Economista (empresite.eleconomista.es)
  3. UNEF Asociados (unef.es/asociados/) — directorio sectorial solar
  4. Kompass España (es.kompass.com)

Arquitectura:
  - Fase 1: Recopilar datos básicos (nombre, web, URL de detalle) de todas las páginas
            de listado sin salir de ellas.
  - Fase 2: Visitar páginas de detalle para enriquecer con email y NIF.
  - Fase 3: Guardar todos los leads en la base de datos y exportar CSV.

Uso:
    python src/scraper.py
    SEARCH_KEYWORD="energía solar" python src/scraper.py
    HEADLESS=false python src/scraper.py   # modo visible para depuración
    MAX_PAGES=5 python src/scraper.py
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

# Ajustar path para importar módulos locales cuando se ejecuta desde src/
sys.path.insert(0, str(Path(__file__).parent))

from models import init_db
from utils import setup_logger, save_lead, export_to_csv, clean_text, extract_email, extract_nif, normalize_url

# ─────────────────────────────────────────────
# Configuración
# ─────────────────────────────────────────────

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

KEYWORD = os.getenv("SEARCH_KEYWORD", "instalaciones solares")
MAX_PAGES = int(os.getenv("MAX_PAGES", "5"))
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/leads.db")
LOG_DIR = os.getenv("LOG_DIR", "logs")
HEADLESS = os.getenv("HEADLESS", "true").lower() != "false"

# Resolver rutas relativas al directorio raíz del proyecto
PROJECT_ROOT = Path(__file__).parent.parent
db_path_raw = DATABASE_URL.replace("sqlite:///", "")
if not Path(db_path_raw).is_absolute():
    DATABASE_URL = f"sqlite:///{PROJECT_ROOT / db_path_raw}"
LOG_DIR = str(PROJECT_ROOT / LOG_DIR)

logger = setup_logger(LOG_DIR)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def random_delay(min_s: float = 1.2, max_s: float = 3.0) -> None:
    """Pausa aleatoria para simular comportamiento humano."""
    time.sleep(random.uniform(min_s, max_s))


def clean_url(url: Optional[str]) -> Optional[str]:
    """Elimina parámetros UTM de una URL."""
    if not url:
        return None
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query, keep_blank_values=True)
        for utm in ["utm_campaign", "utm_source", "utm_medium", "utm_content", "utm_term"]:
            qs.pop(utm, None)
        new_query = "&".join(f"{k}={v[0]}" for k, v in qs.items())
        cleaned = urlunparse(parsed._replace(query=new_query))
        # Filtrar URLs no válidas
        if cleaned and not cleaned.startswith(("javascript:", "tel:", "mailto:", "#")):
            return cleaned
        return None
    except Exception:
        return url


def extract_email_from_html(html: str) -> Optional[str]:
    """Extrae el primer email encontrado en HTML."""
    match = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", html)
    return match.group(0).lower() if match else None


def extract_nif_from_html(html: str) -> Optional[str]:
    """Extrae un NIF/CIF español del HTML."""
    pattern = r"\b([A-HJ-NP-SUVW]\d{7}[0-9A-J]|\d{8}[A-Z]|[XYZ]\d{7}[A-Z])\b"
    match = re.search(pattern, html.upper())
    return match.group(0) if match else None


def is_valid_company_name(name: str) -> bool:
    """Filtra nombres que claramente no son empresas."""
    if not name or len(name) < 3 or len(name) > 120:
        return False
    skip_words = [
        "inicio", "contacto", "sobre nosotros", "noticias", "política",
        "aviso legal", "cookies", "quiénes somos", "facebook", "twitter",
        "linkedin", "youtube", "instagram", "whatsapp", "ver teléfono",
        "ver galería", "danos tu opinión", "más negocios", "siguiente",
        "anterior", "filtrar", "ordenar", "relevancia", "opiniones",
        "diseñado por", "contacta con nosotros", "mantente informado",
        "apúntate", "newsletter", "prioridades", "análisis", "sellos",
        "asociados", "quiénes", "informe", "condiciones", "privacidad",
        "no hemos encontrado", "página no encontrada", "error 404",
        "acceso denegado", "loading", "cargando",
    ]
    name_lower = name.lower()
    return not any(w in name_lower for w in skip_words)


def try_extract_email_from_website(page: Page, web_url: str, log) -> Optional[str]:
    """
    Visita la web de la empresa e intenta extraer un email de contacto.
    Busca en la página principal y en /contacto o /contact si no encuentra.

    Returns:
        Email encontrado o None.
    """
    if not web_url or not web_url.startswith("http"):
        return None
    try:
        page.goto(web_url, timeout=15_000, wait_until="domcontentloaded")
        random_delay(0.8, 1.5)
        html = page.content()
        email = extract_email_from_html(html)
        if email:
            return email
        # Intentar página de contacto
        contact_paths = ["/contacto", "/contacto/", "/contact", "/contact/", "/contacta", "/contactanos"]
        base = web_url.rstrip("/")
        for path in contact_paths:
            try:
                page.goto(base + path, timeout=10_000, wait_until="domcontentloaded")
                random_delay(0.5, 1.0)
                html = page.content()
                email = extract_email_from_html(html)
                if email:
                    return email
            except Exception:
                continue
    except Exception as exc:
        log.debug(f"Error al visitar web '{web_url}': {exc}")
    return None


# ─────────────────────────────────────────────
# Scraper 1: Páginas Amarillas
# Selectores validados en producción (2024-04)
# ─────────────────────────────────────────────

def scrape_paginas_amarillas(page: Page, session, keyword: str, max_pages: int) -> int:
    """
    Extrae empresas de paginasamarillas.es.

    Estrategia en dos fases:
      Fase 1 — Recopilar datos básicos de TODAS las páginas de listado.
      Fase 2 — Visitar fichas de detalle para enriquecer con email.

    Selectores validados:
      - Tarjeta:       div.listado-item
      - Nombre:        h2 (texto, eliminando '+info')
      - Web (listado): a.web
      - URL detalle:   a:first-of-type[href*='/f/']
      - Web (detalle): a.sitio-web
      - Email:         a[href^='mailto:'] o regex en HTML

    Returns:
        Número de leads nuevos insertados.
    """
    source = "Páginas Amarillas"
    keyword_slug = keyword.replace(" ", "-").lower()
    raw_leads: List[Dict] = []

    # ── FASE 1: Recopilar datos de todas las páginas de listado ──
    for page_num in range(1, max_pages + 1):
        url = (
            f"https://www.paginasamarillas.es/search/{keyword_slug}"
            f"/all-ma/all-pr/all-is/all-ci/all-ba/all-pu/all-nc/{page_num}"
            f"?what={keyword.replace(' ', '+')}&qc=true"
        )
        logger.info(f"[{source}] Listado página {page_num}: {url}")

        try:
            page.goto(url, timeout=30_000, wait_until="domcontentloaded")
            random_delay(2, 4)
        except PWTimeout:
            logger.warning(f"[{source}] Timeout en página {page_num}. Fin de paginación.")
            break

        try:
            page.wait_for_selector("div.listado-item", timeout=12_000)
        except PWTimeout:
            logger.warning(f"[{source}] Sin tarjetas en página {page_num}. Fin de paginación.")
            break

        # Extraer datos de todas las tarjetas vía JavaScript (más robusto)
        cards_data = page.evaluate("""
            () => {
                const cards = Array.from(document.querySelectorAll('div.listado-item'));
                return cards.map(card => {
                    const h2 = card.querySelector('h2');
                    const nombre = h2 ? h2.innerText.replace('+info','').trim() : '';

                    const webEl = card.querySelector('a.web');
                    let web = webEl ? webEl.href : '';
                    // Limpiar UTM
                    try {
                        if (web) {
                            const u = new URL(web);
                            ['utm_campaign','utm_source','utm_medium','utm_content','utm_term']
                                .forEach(p => u.searchParams.delete(p));
                            web = u.toString();
                        }
                    } catch(e) {}

                    // URL de detalle: primer enlace con /f/ en href
                    const detailLinks = Array.from(card.querySelectorAll('a[href*="/f/"]'));
                    const detailHref = detailLinks.length > 0 ? detailLinks[0].href : '';

                    return { nombre, web, detail_href: detailHref };
                }).filter(d => d.nombre.length > 0);
            }
        """)

        logger.info(f"[{source}] Encontradas {len(cards_data)} tarjetas en página {page_num}.")
        raw_leads.extend(cards_data)

        # Verificar si hay siguiente página (botón de paginación)
        has_next = page.evaluate("""
            () => {
                const nextLinks = Array.from(document.querySelectorAll('a[rel="next"], .paginacion a'));
                return nextLinks.length > 0 && nextLinks.some(a => a.href && a.href !== window.location.href);
            }
        """)
        if not has_next:
            logger.info(f"[{source}] No hay más páginas después de la {page_num}.")
            break

        random_delay(2, 3)

    logger.info(f"[{source}] Total tarjetas recopiladas: {len(raw_leads)}")

    # ── FASE 2: Visitar fichas de detalle para enriquecer con email ──
    total_saved = 0
    for lead_data in raw_leads:
        nombre = clean_text(lead_data.get("nombre", "").replace("+info", ""))
        if not nombre or not is_valid_company_name(nombre):
            continue

        web = clean_url(lead_data.get("web")) or None
        detail_href = lead_data.get("detail_href", "")
        email = None

        if detail_href and "paginasamarillas.es/f/" in detail_href:
            try:
                page.goto(detail_href, timeout=20_000, wait_until="domcontentloaded")
                random_delay(1.0, 2.0)

                # Web desde ficha de detalle (si no se obtuvo del listado)
                if not web:
                    web_el = page.query_selector("a.sitio-web")
                    if web_el:
                        web = clean_url(web_el.get_attribute("href"))

                # Email: enlace mailto o regex en HTML de la ficha
                email_el = page.query_selector("a[href^='mailto:']")
                if email_el:
                    email = email_el.get_attribute("href").replace("mailto:", "").strip()
                if not email:
                    html = page.content()
                    email = extract_email_from_html(html)

            except Exception as exc:
                logger.debug(f"[{source}] Error en detalle '{nombre}': {exc}")

        # Si aún no hay email, intentar extraerlo de la web de la empresa
        if not email and web:
            email = try_extract_email_from_website(page, web, logger)

        saved = save_lead(session, {
            "nombre": nombre,
            "web": web,
            "email": email,
            "fuente": source,
            "keyword": keyword,
        }, logger)
        if saved:
            total_saved += 1

        random_delay(0.5, 1.2)

    logger.info(f"[{source}] Total leads nuevos insertados: {total_saved}")
    return total_saved


# ─────────────────────────────────────────────
# Scraper 2: Empresite (El Economista)
# ─────────────────────────────────────────────

def scrape_empresite(page: Page, session, keyword: str, max_pages: int) -> int:
    """
    Extrae empresas de empresite.eleconomista.es.
    URL validada: /buscar/?q=<keyword>

    Returns:
        Número de leads nuevos insertados.
    """
    source = "Empresite"
    total_saved = 0
    keyword_encoded = keyword.replace(" ", "+")

    for page_num in range(1, max_pages + 1):
        if page_num == 1:
            url = f"https://empresite.eleconomista.es/buscar/?q={keyword_encoded}"
        else:
            url = f"https://empresite.eleconomista.es/buscar/?q={keyword_encoded}&page={page_num}"

        logger.info(f"[{source}] Página {page_num}: {url}")

        try:
            page.goto(url, timeout=30_000, wait_until="domcontentloaded")
            random_delay(2, 3)
        except PWTimeout:
            logger.warning(f"[{source}] Timeout en página {page_num}.")
            break

        # Extraer datos vía JavaScript
        cards_data = page.evaluate("""
            () => {
                // Intentar múltiples selectores de tarjeta
                let cards = Array.from(document.querySelectorAll('.empresa, .company-item, article.item, .result-item'));
                if (!cards.length) {
                    cards = Array.from(document.querySelectorAll('article, [class*="empresa"], [class*="company"]'));
                }
                if (!cards.length) return [];

                return cards.slice(0, 30).map(card => {
                    const nameEl = card.querySelector('h2 a, h3 a, .nombre a, a.empresa-nombre, h2, h3');
                    const nombre = nameEl ? nameEl.innerText.trim() : '';

                    const linkEl = card.querySelector('h2 a, h3 a, .nombre a, a[href*="/empresa/"]');
                    const href = linkEl ? linkEl.href : '';

                    const webEl = card.querySelector('a[href*="http"]:not([href*="eleconomista"]):not([href*="empresite"])');
                    const web = webEl ? webEl.href : '';

                    const emailEl = card.querySelector('a[href^="mailto:"]');
                    const email = emailEl ? emailEl.href.replace('mailto:', '') : '';

                    return { nombre, href, web, email };
                }).filter(d => d.nombre.length > 2);
            }
        """)

        if not cards_data:
            logger.warning(f"[{source}] Sin tarjetas en página {page_num}. Intentando extracción alternativa.")
            # Fallback: buscar en el HTML completo
            html = page.content()
            names = re.findall(r'<(?:h[23])[^>]*>\s*(?:<a[^>]*>)?([A-ZÁÉÍÓÚÑ][^<]{4,80})(?:</a>)?</(?:h[23])>', html)
            webs = re.findall(r'href="(https?://(?!empresite|eleconomista)[^"]{10,100})"', html)
            emails = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", html)
            for i, name in enumerate(names[:20]):
                if not is_valid_company_name(name):
                    continue
                saved = save_lead(session, {
                    "nombre": clean_text(name),
                    "web": webs[i] if i < len(webs) else None,
                    "email": emails[i] if i < len(emails) else None,
                    "fuente": source,
                    "keyword": keyword,
                }, logger)
                if saved:
                    total_saved += 1
            break

        logger.info(f"[{source}] Encontradas {len(cards_data)} tarjetas en página {page_num}.")

        for lead_data in cards_data:
            nombre = clean_text(lead_data.get("nombre", ""))
            if not nombre or not is_valid_company_name(nombre):
                continue

            web = clean_url(lead_data.get("web")) or None
            email = lead_data.get("email") or None

            # Visitar detalle si hay enlace y faltan datos
            detail_href = lead_data.get("href", "")
            if detail_href and (not web or not email):
                try:
                    page.goto(detail_href, timeout=20_000, wait_until="domcontentloaded")
                    random_delay(1, 2)
                    html = page.content()

                    if not web:
                        web_el = page.query_selector("a.web, .web a, a[href*='http']:not([href*='eleconomista']):not([href*='empresite'])")
                        web = web_el.get_attribute("href") if web_el else clean_url(
                            re.search(r'href="(https?://(?!empresite|eleconomista)[^"]{10,100})"', html) and
                            re.search(r'href="(https?://(?!empresite|eleconomista)[^"]{10,100})"', html).group(1)
                        )

                    if not email:
                        email_el = page.query_selector("a[href^='mailto:']")
                        email = email_el.get_attribute("href").replace("mailto:", "") if email_el else extract_email_from_html(html)

                except Exception as exc:
                    logger.debug(f"[{source}] Error en detalle '{nombre}': {exc}")

            saved = save_lead(session, {
                "nombre": nombre,
                "web": web,
                "email": email,
                "fuente": source,
                "keyword": keyword,
            }, logger)
            if saved:
                total_saved += 1

            random_delay(0.5, 1.5)

        random_delay(2, 3)

    logger.info(f"[{source}] Total leads nuevos: {total_saved}")
    return total_saved


# ─────────────────────────────────────────────
# Scraper 3: UNEF Asociados (directorio solar)
# ─────────────────────────────────────────────

def scrape_unef_asociados(page: Page, session, keyword: str) -> int:
    """
    Extrae empresas asociadas a UNEF (Unión Española Fotovoltaica).
    El directorio más relevante del sector solar en España.

    Returns:
        Número de leads nuevos insertados.
    """
    source = "UNEF Asociados"
    total_saved = 0
    url = "https://unef.es/asociados/"

    logger.info(f"[{source}] Accediendo a: {url}")

    try:
        page.goto(url, timeout=30_000, wait_until="domcontentloaded")
        random_delay(3, 5)
    except PWTimeout:
        logger.warning(f"[{source}] Timeout. Abortando fuente.")
        return 0

    # Scroll para cargar contenido dinámico
    for _ in range(5):
        page.evaluate("window.scrollBy(0, window.innerHeight * 0.8)")
        random_delay(1, 2)

    # Extraer datos vía JavaScript con múltiples estrategias
    cards_data = page.evaluate("""
        () => {
            const results = [];

            // Estrategia 1: Buscar elementos con clase 'asociado' o 'member'
            let cards = Array.from(document.querySelectorAll(
                '.asociado, .asociado-item, .member, .member-item, [class*="asociado"], [class*="member"]'
            ));

            // Estrategia 2: Buscar en grids o listas
            if (!cards.length) {
                cards = Array.from(document.querySelectorAll('.grid-item, .wp-block-column, .elementor-widget-wrap'));
            }

            // Estrategia 3: Buscar en cualquier elemento que tenga un enlace externo
            if (!cards.length) {
                const externalLinks = Array.from(document.querySelectorAll('a[href*="http"]:not([href*="unef.es"])'));
                externalLinks.forEach(link => {
                    const text = link.innerText.trim();
                    if (text.length > 3 && text.length < 100 && !text.match(/^(http|www)/)) {
                        results.push({
                            nombre: text,
                            web: link.href,
                            email: ''
                        });
                    }
                });
                return results;
            }

            cards.forEach(card => {
                const nameEl = card.querySelector('h2, h3, h4, strong, .nombre, .name, p strong');
                const nombre = nameEl ? nameEl.innerText.trim() : '';
                if (!nombre || nombre.length < 3) return;

                const webEl = card.querySelector('a[href*="http"]:not([href*="unef.es"])');
                const web = webEl ? webEl.href : '';

                const emailEl = card.querySelector('a[href^="mailto:"]');
                const email = emailEl ? emailEl.href.replace('mailto:', '') : '';

                results.push({ nombre, web, email });
            });

            return results;
        }
    """)

    # Filtrar resultados válidos
    valid_leads = [d for d in cards_data if d.get("nombre") and is_valid_company_name(d.get("nombre", ""))]
    logger.info(f"[{source}] Encontradas {len(valid_leads)} empresas válidas.")

    for lead_data in valid_leads:
        nombre = clean_text(lead_data.get("nombre", ""))
        web = clean_url(lead_data.get("web")) or None
        email = lead_data.get("email") or None

        saved = save_lead(session, {
            "nombre": nombre,
            "web": web,
            "email": email,
            "fuente": source,
            "keyword": keyword,
        }, logger)
        if saved:
            total_saved += 1

    logger.info(f"[{source}] Total leads nuevos: {total_saved}")
    return total_saved


# ─────────────────────────────────────────────
# Scraper 4: Kompass España
# ─────────────────────────────────────────────

def scrape_kompass(page: Page, session, keyword: str, max_pages: int) -> int:
    """
    Extrae empresas de es.kompass.com.

    Returns:
        Número de leads nuevos insertados.
    """
    source = "Kompass España"
    total_saved = 0
    keyword_encoded = keyword.replace(" ", "%20")

    for page_num in range(1, max_pages + 1):
        url = (
            f"https://es.kompass.com/searchCompanies?text={keyword_encoded}"
            f"&country=ES&page={page_num}"
        )
        logger.info(f"[{source}] Página {page_num}: {url}")

        try:
            page.goto(url, timeout=30_000, wait_until="domcontentloaded")
            random_delay(2, 4)
        except PWTimeout:
            logger.warning(f"[{source}] Timeout en página {page_num}.")
            break

        cards_data = page.evaluate("""
            () => {
                let cards = Array.from(document.querySelectorAll(
                    '.companyCard, .k-card, [class*="companyCard"], [class*="CompanyCard"], .result-item'
                ));
                if (!cards.length) {
                    cards = Array.from(document.querySelectorAll('article, [class*="result"]'));
                }
                return cards.slice(0, 25).map(card => {
                    const nameEl = card.querySelector('h2, h3, .companyName, [class*="Name"], a.name');
                    const nombre = nameEl ? nameEl.innerText.trim() : '';
                    const webEl = card.querySelector('a[href*="http"]:not([href*="kompass"])');
                    const web = webEl ? webEl.href : '';
                    const emailEl = card.querySelector('a[href^="mailto:"]');
                    const email = emailEl ? emailEl.href.replace('mailto:', '') : '';
                    return { nombre, web, email };
                }).filter(d => d.nombre.length > 2);
            }
        """)

        if not cards_data:
            logger.warning(f"[{source}] Sin tarjetas en página {page_num}.")
            break

        logger.info(f"[{source}] Encontradas {len(cards_data)} tarjetas en página {page_num}.")

        for lead_data in cards_data:
            nombre = clean_text(lead_data.get("nombre", ""))
            if not nombre or not is_valid_company_name(nombre):
                continue

            saved = save_lead(session, {
                "nombre": nombre,
                "web": clean_url(lead_data.get("web")) or None,
                "email": lead_data.get("email") or None,
                "fuente": source,
                "keyword": keyword,
            }, logger)
            if saved:
                total_saved += 1

        random_delay(2, 4)

    logger.info(f"[{source}] Total leads nuevos: {total_saved}")
    return total_saved


# ─────────────────────────────────────────────
# Orquestador principal
# ─────────────────────────────────────────────

# Pool de User-Agents para rotación
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


def new_browser_context(browser, user_agent: Optional[str] = None):
    """Crea un nuevo contexto de navegador con User-Agent rotado."""
    ua = user_agent or random.choice(USER_AGENTS)
    return browser.new_context(
        user_agent=ua,
        viewport={"width": 1366, "height": 768},
        locale="es-ES",
        extra_http_headers={"Accept-Language": "es-ES,es;q=0.9"},
    )


def main() -> None:
    logger.info("=" * 60)
    logger.info(f"Iniciando scraper | keyword='{KEYWORD}' | max_pages={MAX_PAGES}")
    logger.info(f"Base de datos: {DATABASE_URL}")
    logger.info(f"Headless: {HEADLESS}")
    logger.info("=" * 60)

    # Inicializar base de datos
    session = init_db(DATABASE_URL)

    grand_total = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )

        # ── Fuente 1: Páginas Amarillas ──
        # Nueva sesión de navegador para evitar bloqueos anti-scraping
        logger.info("─" * 40)
        logger.info("Iniciando fuente: Páginas Amarillas")
        logger.info("─" * 40)
        try:
            ctx1 = new_browser_context(browser)
            page1 = ctx1.new_page()
            n = scrape_paginas_amarillas(page1, session, KEYWORD, MAX_PAGES)
            grand_total += n
            ctx1.close()
        except Exception as exc:
            logger.error(f"Error crítico en Páginas Amarillas: {exc}")

        random_delay(3, 6)  # Pausa entre fuentes

        # ── Fuente 2: Empresite ──
        logger.info("─" * 40)
        logger.info("Iniciando fuente: Empresite")
        logger.info("─" * 40)
        try:
            ctx2 = new_browser_context(browser)
            page2 = ctx2.new_page()
            n = scrape_empresite(page2, session, KEYWORD, MAX_PAGES)
            grand_total += n
            ctx2.close()
        except Exception as exc:
            logger.error(f"Error crítico en Empresite: {exc}")

        random_delay(3, 6)

        # ── Fuente 3: UNEF Asociados ──
        logger.info("─" * 40)
        logger.info("Iniciando fuente: UNEF Asociados")
        logger.info("─" * 40)
        try:
            ctx3 = new_browser_context(browser)
            page3 = ctx3.new_page()
            n = scrape_unef_asociados(page3, session, KEYWORD)
            grand_total += n
            ctx3.close()
        except Exception as exc:
            logger.error(f"Error crítico en UNEF: {exc}")

        random_delay(3, 6)

        # ── Fuente 4: Kompass España ──
        logger.info("─" * 40)
        logger.info("Iniciando fuente: Kompass España")
        logger.info("─" * 40)
        try:
            ctx4 = new_browser_context(browser)
            page4 = ctx4.new_page()
            n = scrape_kompass(page4, session, KEYWORD, MAX_PAGES)
            grand_total += n
            ctx4.close()
        except Exception as exc:
            logger.error(f"Error crítico en Kompass: {exc}")

        browser.close()

    # Exportar a CSV
    csv_path = str(PROJECT_ROOT / "data" / "leads.csv")
    export_to_csv(session, csv_path, logger)
    session.close()

    logger.info("=" * 60)
    logger.info(f"Scraping completado. Total leads nuevos insertados: {grand_total}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
