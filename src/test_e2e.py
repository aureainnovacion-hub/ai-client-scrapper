"""
test_e2e.py
-----------
Prueba end-to-end del pipeline completo con 1 página de resultados.
Verifica que el scraper extrae leads, NIFs y que la BDNS responde.
"""

import sys
import os
from pathlib import Path

# Configurar entorno de prueba
os.environ["SEARCH_KEYWORD"] = "instalaciones solares"
os.environ["MAX_PAGES"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///data/leads_test.db"
os.environ["LOG_DIR"] = "logs"
os.environ["HEADLESS"] = "true"

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import init_db, Lead
from src.utils import setup_logger, export_to_csv
from src.scraper import run_all_scrapers
from src.enrich_leads import enrich_leads
from services.bdns_service import check_subsidies

logger = setup_logger("logs")

def test_full_pipeline():
    print("=" * 60)
    print("  PRUEBA END-TO-END DEL PIPELINE COMPLETO")
    print("=" * 60)
    
    # Limpiar base de datos de prueba
    test_db = Path("data/leads_test.db")
    if test_db.exists():
        test_db.unlink()
        print("  Base de datos de prueba limpiada.")
    
    # ── FASE 1: Scraping ──────────────────────────────────────────────────
    print("\n[1/3] Ejecutando scraper (1 página)...")
    try:
        run_all_scrapers()
    except Exception as exc:
        print(f"  ❌ Error en scraper: {exc}")
        return False
    
    # Verificar resultados del scraping
    session = init_db(f"sqlite:///{test_db}")
    leads = session.query(Lead).all()
    
    print(f"\n  Leads encontrados: {len(leads)}")
    leads_con_web = [l for l in leads if l.web]
    leads_con_nif = [l for l in leads if l.nif]
    leads_con_email = [l for l in leads if l.email]
    
    print(f"  Con URL web:  {len(leads_con_web)}/{len(leads)}")
    print(f"  Con NIF/CIF:  {len(leads_con_nif)}/{len(leads)}")
    print(f"  Con email:    {len(leads_con_email)}/{len(leads)}")
    
    print("\n  Muestra de leads (primeros 5):")
    for lead in leads[:5]:
        print(f"    · {lead.nombre[:40]:<40} | NIF: {lead.nif or '—':12} | Email: {lead.email or '—'}")
    
    if not leads:
        print("  ❌ No se encontraron leads. Verifica la conexión a Páginas Amarillas.")
        session.close()
        return False
    
    # ── FASE 2: Enriquecimiento BDNS ──────────────────────────────────────
    print("\n[2/3] Ejecutando enriquecimiento BDNS...")
    session.close()
    
    try:
        enrich_leads()
    except Exception as exc:
        print(f"  ❌ Error en enriquecimiento: {exc}")
        return False
    
    # Verificar resultados del enriquecimiento
    session = init_db(f"sqlite:///{test_db}")
    leads_enriquecidos = session.query(Lead).filter(Lead.num_concesiones > 0).all()
    leads_prioritarios = session.query(Lead).filter(Lead.es_prioritario == True).all()
    
    print(f"\n  Leads con subvenciones BDNS: {len(leads_enriquecidos)}")
    print(f"  Leads prioritarios:          {len(leads_prioritarios)}")
    
    if leads_enriquecidos:
        print("\n  Leads con subvenciones encontradas:")
        for lead in leads_enriquecidos[:3]:
            print(f"    · {lead.nombre[:40]:<40} | {lead.num_concesiones} concesiones | {lead.total_subvenciones:,.0f}€")
    
    # ── FASE 3: Exportar CSV ──────────────────────────────────────────────
    print("\n[3/3] Exportando resultados a CSV...")
    csv_path = "data/leads_test.csv"
    export_to_csv(session, csv_path, logger)
    
    if Path(csv_path).exists():
        print(f"  ✅ CSV exportado: {csv_path} ({Path(csv_path).stat().st_size} bytes)")
    
    session.close()
    
    # ── Resumen ───────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  RESUMEN FINAL")
    print("=" * 60)
    print(f"  Total leads:              {len(leads)}")
    print(f"  Con NIF/CIF:              {len(leads_con_nif)}")
    print(f"  Con email:                {len(leads_con_email)}")
    print(f"  Con subvenciones BDNS:    {len(leads_enriquecidos)}")
    print(f"  Prioritarios para Aurea:  {len(leads_prioritarios)}")
    
    if len(leads) > 0:
        print("\n  ✅ Pipeline completado con éxito")
        return True
    else:
        print("\n  ⚠️  Pipeline completado pero sin leads")
        return False


if __name__ == "__main__":
    test_full_pipeline()
