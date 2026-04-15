"""
run_pipeline.py
---------------
Orquestador principal del proyecto ai-client-scrapper.

Ejecuta el pipeline completo en orden:
  1. Scraper       → obtención de leads desde Páginas Amarillas
  2. Enriquecimiento BDNS → consulta de subvenciones por NIF/CIF
  3. Mailer        → envío de emails comerciales (si está configurado)
"""

import subprocess
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent
load_dotenv(PROJECT_ROOT / ".env")


def run_script(script_path: Path, env_vars: dict = None) -> bool:
    """Ejecuta un script Python como subproceso y muestra su salida en tiempo real."""
    print(f"\n{'='*60}")
    print(f">>> Ejecutando: {script_path.name}")
    print(f"{'='*60}")

    current_env = os.environ.copy()
    if env_vars:
        current_env.update({k: str(v) for k, v in env_vars.items()})

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            env=current_env,
            check=True,
            capture_output=False,
            text=True,
        )
        print(f">>> {script_path.name} completado con éxito.")
        return True
    except subprocess.CalledProcessError as exc:
        print(f">>> ERROR en {script_path.name} (código {exc.returncode})")
        return False
    except FileNotFoundError:
        print(f">>> ERROR: No se encontró el script {script_path}")
        return False


def main():
    print("=" * 60)
    print("  PIPELINE AI CLIENT SCRAPPER — Aurea Innovación")
    print("=" * 60)

    # Leer MAX_PAGES del entorno (por defecto 3 para el pipeline automático)
    max_pages = os.getenv("MAX_PAGES", "3")

    # ── 1. Scraper ────────────────────────────────────────────────────────
    scraper_ok = run_script(
        PROJECT_ROOT / "src" / "scraper.py",
        env_vars={"MAX_PAGES": max_pages},
    )
    if not scraper_ok:
        print("\n[PIPELINE] Detenido por error en el Scraper.")
        sys.exit(1)

    # ── 2. Enriquecimiento BDNS ───────────────────────────────────────────
    bdns_ok = run_script(PROJECT_ROOT / "src" / "enrich_leads.py")
    if not bdns_ok:
        print("\n[PIPELINE] Detenido por error en el Enriquecimiento BDNS.")
        sys.exit(1)

    # ── 3. Mailer ─────────────────────────────────────────────────────────
    # El mailer es opcional: si falla, el pipeline continúa con advertencia
    mailer_ok = run_script(PROJECT_ROOT / "src" / "mailer.py")
    if not mailer_ok:
        print("\n[PIPELINE] Advertencia: el Mailer finalizó con errores.")
        print("[PIPELINE] Revisa la configuración SMTP en el archivo .env")

    print("\n" + "=" * 60)
    print("  PIPELINE FINALIZADO")
    print("=" * 60)


if __name__ == "__main__":
    main()
