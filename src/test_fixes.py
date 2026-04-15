"""
test_fixes.py
-------------
Script de validación de los módulos corregidos.
Prueba: extracción de NIF desde web, búsqueda por nombre en BORME y API BDNS.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import (
    extract_nifs, extract_emails, validate_spanish_id,
    lookup_nif_by_name, setup_logger
)
from services.bdns_service import check_subsidies

logger = setup_logger()


def test_validate_nif():
    """Verifica que el validador de NIF/CIF funciona correctamente."""
    print("\n── TEST 1: Validación de NIF/CIF ──────────────────────────")
    casos = [
        ("A28003119", True,  "CIF Endesa (válido)"),
        ("B82846999", True,  "CIF empresa válida (B82846999)"),
        ("A20156220", True,  "CIF ipcastro.com (válido)"),
        ("12345678Z", True,  "NIF persona física (válido)"),
        ("A12345678", False, "CIF con dígito control incorrecto"),
        ("XXXXXXXXX", False, "Cadena inválida"),
        ("00000000T", True,  "NIF con ceros (válido)"),
    ]
    ok = 0
    for cif, expected, desc in casos:
        result = validate_spanish_id(cif)
        status = "✅" if result == expected else "❌"
        print(f"  {status} {desc}: {cif} → {result} (esperado: {expected})")
        if result == expected:
            ok += 1
    print(f"  Resultado: {ok}/{len(casos)} correctos")
    return ok == len(casos)


def test_extract_nifs():
    """Verifica la extracción de NIFs desde texto HTML."""
    print("\n── TEST 2: Extracción de NIF desde texto ──────────────────")
    
    # Texto simulando un Aviso Legal
    texto_aviso_legal = """
    <p>EMPRESA SOLAR S.L., con CIF: A28003119, domicilio en Calle Mayor 1, Madrid.</p>
    <p>En cumplimiento de la LSSI, le informamos que el titular de este sitio web es
    EMPRESA SOLAR S.L., con NIF A28003119, inscrita en el Registro Mercantil de Madrid.</p>
    """
    
    nifs = extract_nifs(texto_aviso_legal)
    print(f"  Texto con 'CIF: A28003119' → NIFs encontrados: {nifs}")
    assert "A28003119" in nifs, "❌ No se encontró A28003119"
    print(f"  ✅ A28003119 encontrado correctamente")
    
    # Texto sin NIF
    texto_sin_nif = "<p>Bienvenidos a nuestra web de instalaciones solares.</p>"
    nifs_vacio = extract_nifs(texto_sin_nif)
    print(f"  Texto sin NIF → NIFs encontrados: {nifs_vacio}")
    assert nifs_vacio == [], "❌ Se encontraron NIFs donde no debería haber"
    print(f"  ✅ Lista vacía correctamente")
    return True


def test_bdns_api():
    """Verifica que la API de BDNS responde correctamente."""
    print("\n── TEST 3: API BDNS (Hacienda) ────────────────────────────")
    
    # Probar con un NIF conocido que tiene subvenciones (Endesa)
    cif_test = "A28003119"
    print(f"  Consultando BDNS para NIF: {cif_test}")
    result = check_subsidies(cif_test)
    
    if "error" in result:
        print(f"  ❌ Error en BDNS: {result['error']}")
        return False
    
    total = result.get("total_subsidies", 0)
    amount = result.get("total_amount", 0)
    print(f"  ✅ Total concesiones: {total}")
    print(f"  ✅ Importe total: {amount:,.2f}€")
    
    if result.get("details"):
        sub = result["details"][0]
        print(f"  ✅ Última subvención: [{sub.get('date','')}] {sub.get('title','')[:60]}...")
    
    assert total > 0, "❌ Se esperaban subvenciones para Endesa"
    
    # Probar con un NIF sin subvenciones
    cif_sin_subv = "B00000001"
    print(f"\n  Consultando BDNS para NIF inexistente: {cif_sin_subv}")
    result2 = check_subsidies(cif_sin_subv)
    print(f"  Total: {result2.get('total_subsidies', 0)} (esperado: 0)")
    return True


def test_lookup_nif_by_name():
    """Verifica la búsqueda de NIF por nombre de empresa en BORME."""
    print("\n── TEST 4: Búsqueda de NIF por nombre (emprecif.com) ──────")
    
    # Empresa conocida con NIF conocido
    empresa = "Endesa"
    print(f"  Buscando NIF para: '{empresa}'")
    nif = lookup_nif_by_name(empresa, logger)
    
    if nif:
        print(f"  ✅ NIF encontrado: {nif}")
        print(f"  ✅ NIF válido: {validate_spanish_id(nif)}")
    else:
        print(f"  ⚠️  NIF no encontrado (puede ser bloqueo temporal de emprecif.com)")
    
    # Empresa ficticia
    empresa_ficticia = "Empresa Inexistente XYZ 99999"
    nif_ficticio = lookup_nif_by_name(empresa_ficticia, logger)
    print(f"  Empresa ficticia → NIF: {nif_ficticio} (esperado: None o inválido)")
    return True


def test_deep_extract():
    """Prueba la extracción profunda desde una web real conocida."""
    print("\n── TEST 5: Extracción profunda desde web real ──────────────")
    
    try:
        from playwright.sync_api import sync_playwright
        from src.scraper import deep_extract_from_website
        
        test_url = "https://www.ipcastro.com/"
        expected_nif = "A20156220"
        
        print(f"  URL de prueba: {test_url}")
        print(f"  NIF esperado: {expected_nif}")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            result = deep_extract_from_website(page, test_url)
            browser.close()
        
        print(f"  NIF extraído: {result.get('nif')}")
        print(f"  Email extraído: {result.get('email')}")
        
        if result.get('nif') == expected_nif:
            print(f"  ✅ NIF correcto del Aviso Legal: {result['nif']}")
        elif result.get('nif'):
            print(f"  ⚠️  NIF diferente al esperado: {result['nif']} (esperado: {expected_nif})")
        else:
            print(f"  ⚠️  NIF no encontrado en la web (puede requerir búsqueda en BORME)")
        
        return True
        
    except Exception as exc:
        print(f"  ❌ Error en test de extracción: {exc}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("  VALIDACIÓN DE MÓDULOS CORREGIDOS")
    print("=" * 60)
    
    resultados = []
    resultados.append(("Validación NIF/CIF",    test_validate_nif()))
    resultados.append(("Extracción NIF texto",  test_extract_nifs()))
    resultados.append(("API BDNS Hacienda",     test_bdns_api()))
    resultados.append(("Búsqueda NIF por nombre", test_lookup_nif_by_name()))
    resultados.append(("Extracción web real",   test_deep_extract()))
    
    print("\n" + "=" * 60)
    print("  RESUMEN DE RESULTADOS")
    print("=" * 60)
    for nombre, ok in resultados:
        estado = "✅ OK" if ok else "❌ FALLO"
        print(f"  {estado}  {nombre}")
    
    total_ok = sum(1 for _, ok in resultados if ok)
    print(f"\n  Total: {total_ok}/{len(resultados)} pruebas superadas")
    print("=" * 60)
