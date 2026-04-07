# ai-client-scrapper

Scraper automatizado de empresas del sector de **instalaciones solares en España**, construido con [Playwright](https://playwright.dev/python/) y Python 3.10. Los resultados se persisten en una base de datos SQLite local (`leads.db`) y se exportan a CSV.

---

## Características

- Búsqueda automatizada en directorios sectoriales españoles (Páginas Amarillas, Empresite, UNEF Asociados, Kompass España)
- Extracción de: **Nombre de empresa**, **Sitio web**, **NIF** (cuando está disponible) y **Email de contacto**
- **Enriquecimiento de emails**: visita la web de cada empresa para extraer el email de contacto si no está disponible en el directorio
- **Nueva sesión de navegador por fuente** con rotación de User-Agent para evitar bloqueos anti-scraping
- Deduplicación automática por nombre de empresa y fuente
- Persistencia en SQLite mediante SQLAlchemy ORM
- Exportación a CSV en `data/leads.csv`
- Logging estructurado con rotación de archivos (5 MB, 3 backups)
- Configuración completa mediante variables de entorno (`.env`)

---

## Resultados de prueba

Ejecución realizada el **07/04/2026** con `MAX_PAGES=2` y `keyword='instalaciones solares'`:

| Métrica | Valor |
|---|---|
| Total leads extraídos | **30** |
| Leads con sitio web | **20** |
| Leads con email | **6** |
| Fuente principal | Páginas Amarillas |
| Duración aprox. | ~2 minutos |

> **Nota sobre emails**: Páginas Amarillas oculta los emails detrás de formularios de contacto. El scraper visita automáticamente la web de cada empresa para intentar extraer el email. Las webs que usan formularios de contacto sin exponer la dirección en el HTML no pueden ser extraídas sin interacción manual.

---

## Requisitos

| Herramienta | Versión mínima |
|---|---|
| Python | 3.10 |
| pip | 23+ |

---

## Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/<tu-usuario>/ai-client-scrapper.git
cd ai-client-scrapper

# 2. Crear entorno virtual
python3.10 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Instalar navegadores de Playwright
playwright install chromium

# 5. Configurar variables de entorno
cp .env.example .env
# Editar .env según necesidades
```

---

## Uso

```bash
# Ejecutar el scraper con configuración por defecto
python src/scraper.py

# Sobrescribir la palabra clave en tiempo de ejecución
SEARCH_KEYWORD="energía solar" python src/scraper.py

# Cambiar el número máximo de páginas por fuente
MAX_PAGES=5 python src/scraper.py

# Modo visible (no headless) para depuración
HEADLESS=false python src/scraper.py

# Combinación de opciones
SEARCH_KEYWORD="placas fotovoltaicas" MAX_PAGES=3 HEADLESS=false python src/scraper.py
```

---

## Variables de entorno

| Variable | Valor por defecto | Descripción |
|---|---|---|
| `SEARCH_KEYWORD` | `instalaciones solares` | Palabra clave de búsqueda |
| `MAX_PAGES` | `5` | Páginas máximas a scrapear por fuente |
| `DATABASE_URL` | `sqlite:///data/leads.db` | URL de conexión SQLAlchemy |
| `HEADLESS` | `true` | `false` para ver el navegador en acción |
| `LOG_DIR` | `logs` | Directorio de logs |

---

## Estructura del proyecto

```
ai-client-scrapper/
├── src/
│   ├── scraper.py        # Script principal de scraping (4 fuentes)
│   ├── models.py         # Modelos SQLAlchemy (ORM) + init_db()
│   └── utils.py          # Logging, limpieza de datos, exportación CSV
├── data/
│   ├── leads.db          # Base de datos SQLite (generada en ejecución)
│   └── leads.csv         # Exportación CSV (generada en ejecución)
├── logs/
│   └── scraper.log       # Log de ejecución rotativo
├── .env.example          # Plantilla de variables de entorno
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Esquema de la base de datos (`leads`)

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | Identificador autoincremental |
| `nombre` | TEXT | Nombre de la empresa |
| `web` | TEXT | URL del sitio web |
| `nif` | TEXT | NIF/CIF (si está disponible en el directorio) |
| `email` | TEXT | Email de contacto |
| `fuente` | TEXT | Directorio de origen |
| `keyword` | TEXT | Palabra clave de búsqueda |
| `fecha_scraping` | DATETIME | Fecha y hora de extracción (UTC) |

---

## Fuentes de datos

| Directorio | URL | Notas |
|---|---|---|
| Páginas Amarillas | https://www.paginasamarillas.es | Fuente principal. 30 resultados/página. |
| Empresite (El Economista) | https://empresite.eleconomista.es | Búsqueda por actividad. |
| UNEF Asociados | https://unef.es/asociados/ | Directorio oficial del sector solar. |
| Kompass España | https://es.kompass.com | Directorio B2B internacional. |

---

## Arquitectura del scraper

El scraper sigue una arquitectura en **dos fases** por fuente:

1. **Fase de listado**: Recopila todos los datos básicos (nombre, web, URL de detalle) de todas las páginas de resultados sin abandonarlas.
2. **Fase de enriquecimiento**: Visita las fichas de detalle de cada empresa para obtener email y NIF. Si no los encuentra, visita la web de la empresa y su página `/contacto`.

Cada fuente se ejecuta en un **contexto de navegador independiente** con User-Agent rotado para minimizar la detección anti-bot.

---

## Notas técnicas

- **Rate limiting**: Los directorios aplican límites de velocidad. El scraper incluye delays aleatorios (1-4 segundos) entre peticiones y pausas de 3-6 segundos entre fuentes.
- **Anti-scraping**: Si un directorio bloquea el acceso, el scraper registra el error y continúa con la siguiente fuente sin interrumpir la ejecución.
- **Deduplicación**: La restricción `UNIQUE(nombre, fuente)` en la base de datos evita duplicados en ejecuciones sucesivas.
- **NIF**: Solo aparece en directorios que lo publican explícitamente (principalmente Kompass y registros mercantiles). Páginas Amarillas no lo expone.

---

## Licencia

MIT License — uso libre con atribución.
