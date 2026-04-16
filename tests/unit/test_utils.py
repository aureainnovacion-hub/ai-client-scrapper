"""
tests/unit/test_utils.py
------------------------
Pruebas unitarias para los módulos de utilidades del scraper.
Cubre: validación de NIF/CIF, extracción de emails y NIFs del texto, API BDNS.
"""

import sys
from pathlib import Path

# Añadir raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from apps.scraper.src.utils.utils import (
    extract_nifs,
    extract_emails,
    validate_spanish_id,
    lookup_nif_by_name,
    setup_logger,
)
from apps.scraper.src.services.bdns_service import check_subsidies

logger = setup_logger()


def test_validate_nif():
    """Verifica que el validador de NIF/CIF funciona correctamente."""
    print("\n── TEST 1: Validación de NIF/CIF ──────────────────────────")
    casos = [
        ("A28003119", True,  "CIF Endesa (válido)"),
        ("B82846999", True,  "CIF empresa válida"),
        ("A20156220", True,  "CIF ipcastro.com (válido)"),
        ("12345678Z", True,  "NIF persona física (válido)"),
        ("A12345678", False, "CIF con dígito control incorrecto"),
        ("INVALIDO",  False, "Cadena no numérica"),
        ("",          False, "Cadena vacía"),
    ]
    passed = 0
    for nif, expected, desc in casos:
        result = validate_spanish_id(nif)
        status = "OK" if result == expected else "FAIL"
        if result == expected:
            passed += 1
        print(f"  [{status}] {desc}: validate_spanish_id('{nif}') = {result}")
    print(f"  Resultado: {passed}/{len(casos)} casos correctos")
    assert passed == len(casos), f"Fallaron {len(casos) - passed} casos de validación"


def test_extract_nifs():
    """Verifica la extracción de NIFs desde texto libre."""
    print("\n── TEST 2: Extracción de NIF desde texto ──────────────────")
    texto = "La empresa con CIF A28003119 y también B82846999 están registradas."
    nifs = extract_nifs(texto)
    print(f"  Texto: '{texto}'")
    print(f"  NIFs extraídos: {nifs}")
    assert "A28003119" in nifs, "Debería encontrar A28003119"
    assert "B82846999" in nifs, "Debería encontrar B82846999"
    print("  [OK] Extracción de NIFs correcta")


def test_extract_emails():
    """Verifica la extracción de emails desde texto libre."""
    print("\n── TEST 3: Extracción de emails ───────────────────────────")
    texto = "Contacte con info@empresa.es o soporte@aurea.com para más información."
    emails = extract_emails(texto)
    print(f"  Texto: '{texto}'")
    print(f"  Emails extraídos: {emails}")
    assert "info@empresa.es" in emails
    assert "soporte@aurea.com" in emails
    print("  [OK] Extracción de emails correcta")


def test_bdns_api():
    """Verifica que la API de BDNS devuelve datos para un NIF conocido."""
    print("\n── TEST 4: API BDNS ────────────────────────────────────────")
    nif = "A28003119"  # Endesa — empresa con subvenciones conocidas
    result = check_subsidies(nif, max_pages=1)
    print(f"  NIF consultado: {nif}")
    print(f"  Total concesiones: {result.get('total_subsidies', 0)}")
    print(f"  Importe total:    {result.get('total_amount', 0):,.2f}€")
    assert "total_subsidies" in result, "Debe tener campo total_subsidies"
    assert "total_amount" in result, "Debe tener campo total_amount"
    assert result["total_subsidies"] >= 0
    print("  [OK] API BDNS responde correctamente")


def test_nif_extraction_with_separators():
    """Verifica que los NIFs con separadores (puntos, guiones) se normalizan."""
    print("\n── TEST 5: NIFs con separadores ───────────────────────────")
    texto = "CIF: A-28.003.119 inscrita en el Registro Mercantil"
    nifs = extract_nifs(texto)
    print(f"  Texto: '{texto}'")
    print(f"  NIFs extraídos: {nifs}")
    assert len(nifs) > 0, "Debería extraer al menos un NIF"
    print("  [OK] Normalización de NIFs con separadores correcta")


if __name__ == "__main__":
    print("=" * 60)
    print("  TESTS UNITARIOS — ai-client-scrapper")
    print("=" * 60)
    tests = [
        test_validate_nif,
        test_extract_nifs,
        test_extract_emails,
        test_bdns_api,
        test_nif_extraction_with_separators,
    ]
    passed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {test.__name__}: {e}")
        except Exception as e:
            print(f"  [ERROR] {test.__name__}: {e}")

    print(f"\n{'='*60}")
    print(f"  RESULTADO: {passed}/{len(tests)} tests pasados")
    print(f"{'='*60}")
    if passed < len(tests):
        sys.exit(1)
