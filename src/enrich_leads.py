"""
enrich_leads.py
---------------
Enriquece los leads existentes en la base de datos consultando la API pública
de la BDNS (Base de Datos Nacional de Subvenciones) de Hacienda.

Solo procesa leads que tengan NIF/CIF registrado. Para cada uno consulta el
historial de subvenciones concedidas y actualiza los campos correspondientes.
"""

import os
import sys
import time
from dotenv import load_dotenv
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.models import init_db, Lead
from src.utils import setup_logger
from services.bdns_service import check_subsidies

load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/leads.db")
LOG_DIR = os.getenv("LOG_DIR", "logs")

# Resolver rutas relativas desde la raíz del proyecto
db_path_raw = DATABASE_URL.replace("sqlite:///", "")
if not Path(db_path_raw).is_absolute():
    DATABASE_URL = f"sqlite:///{PROJECT_ROOT / db_path_raw}"
LOG_DIR = str(PROJECT_ROOT / LOG_DIR)

logger = setup_logger(LOG_DIR)

# Umbral para marcar un lead como prioritario para la consultoría Aurea
# (empresa que ha recibido subvenciones significativas = cliente potencial)
PRIORITY_MIN_AMOUNT = float(os.getenv("PRIORITY_MIN_AMOUNT", "10000"))
PRIORITY_MIN_COUNT = int(os.getenv("PRIORITY_MIN_COUNT", "2"))


def enrich_leads():
    """
    Recorre todos los leads con NIF registrado y actualiza sus datos de
    subvenciones consultando la API pública de la BDNS (Hacienda).

    Lógica de prioridad:
      - es_prioritario = True si total_subvenciones > PRIORITY_MIN_AMOUNT
                         O si num_concesiones >= PRIORITY_MIN_COUNT
    """
    logger.info("=" * 60)
    logger.info("INICIANDO ENRIQUECIMIENTO BDNS")
    logger.info(f"Base de datos: {DATABASE_URL}")
    logger.info(f"Umbral prioritario: >{PRIORITY_MIN_AMOUNT}€ o >={PRIORITY_MIN_COUNT} concesiones")
    logger.info("=" * 60)

    session = init_db(DATABASE_URL)

    # Obtener todos los leads que tengan NIF registrado
    leads_to_enrich = session.query(Lead).filter(Lead.nif.isnot(None)).all()

    if not leads_to_enrich:
        logger.warning("No se encontraron leads con NIF para enriquecer.")
        logger.warning("Asegúrate de que el scraper haya encontrado NIFs correctamente.")
        session.close()
        return

    logger.info(f"Leads con NIF encontrados: {len(leads_to_enrich)}")

    enriched_count = 0
    no_subsidies_count = 0
    error_count = 0

    for i, lead in enumerate(leads_to_enrich, 1):
        logger.info(f"[{i}/{len(leads_to_enrich)}] Consultando BDNS: {lead.nombre} (NIF: {lead.nif})")

        result = check_subsidies(lead.nif)

        if "error" in result:
            logger.error(f"  → Error BDNS para {lead.nif}: {result['error']}")
            error_count += 1
            # Pausa mayor en caso de error (posible rate-limit)
            time.sleep(2)
            continue

        total_subsidies = result.get("total_subsidies", 0)
        total_amount = result.get("total_amount", 0.0)

        # Actualizar campos del lead
        lead.total_subvenciones = total_amount
        lead.num_concesiones = total_subsidies
        lead.es_prioritario = (
            total_amount > PRIORITY_MIN_AMOUNT
            or total_subsidies >= PRIORITY_MIN_COUNT
        )

        if total_subsidies > 0:
            enriched_count += 1
            logger.info(
                f"  → {total_subsidies} concesiones | "
                f"{total_amount:,.2f}€ | "
                f"Prioritario: {lead.es_prioritario}"
            )
            # Mostrar las 3 subvenciones más recientes como referencia
            for sub in result.get("details", [])[:3]:
                logger.info(
                    f"     · [{sub.get('date','')}] {sub.get('title','')[:80]} "
                    f"— {sub.get('amount',0):,.0f}€"
                )
        else:
            no_subsidies_count += 1
            logger.info(f"  → Sin subvenciones registradas en BDNS")

        # Pausa respetuosa entre consultas a la API de Hacienda
        time.sleep(1.2)

    # Guardar todos los cambios en la base de datos
    try:
        session.commit()
        logger.info("=" * 60)
        logger.info("ENRIQUECIMIENTO COMPLETADO")
        logger.info(f"  Con subvenciones:    {enriched_count}")
        logger.info(f"  Sin subvenciones:    {no_subsidies_count}")
        logger.info(f"  Errores:             {error_count}")
        logger.info("=" * 60)
    except Exception as exc:
        logger.error(f"Error al guardar cambios en la base de datos: {exc}")
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    enrich_leads()
