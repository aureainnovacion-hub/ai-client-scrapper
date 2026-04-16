"""
bdns_service.py
---------------
Servicio para consultar subvenciones en la Base de Datos Nacional de Subvenciones
(BDNS) del Ministerio de Hacienda mediante su API pública REST.

Endpoint oficial: https://www.pap.hacienda.gob.es/bdnstrans/api/concesiones/busqueda
Documentación:   https://www.infosubvenciones.es/bdnstrans/GE/es/inicio
"""

import time
import requests
from typing import Dict, Any

# URL base de la API pública de la BDNS (Hacienda)
BDNS_API_URL = "https://www.pap.hacienda.gob.es/bdnstrans/api/concesiones/busqueda"

# Cabeceras para evitar bloqueos por bot-detection
HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.pap.hacienda.gob.es/bdnstrans/GE/es/concesiones",
}


def check_subsidies(cif: str, max_pages: int = 3) -> Dict[str, Any]:
    """
    Consulta la API pública de la BDNS (Hacienda) para obtener todas las
    subvenciones concedidas a un NIF/CIF dado.

    Parámetros
    ----------
    cif : str
        NIF o CIF de la empresa a consultar (se normaliza internamente).
    max_pages : int
        Número máximo de páginas a paginar (50 registros/página). Por defecto 3
        para cubrir hasta 150 concesiones sin sobrecargar la API.

    Retorna
    -------
    dict con las claves:
        - total_subsidies (int)  : número total de concesiones registradas
        - total_amount   (float) : suma total de importes concedidos en €
        - details        (list)  : lista de concesiones con título, importe,
                                   fecha, organismo y URL de la convocatoria
        - error          (str)   : presente sólo si hubo un error
    """
    if not cif:
        return {"error": "CIF vacío", "total_subsidies": 0, "total_amount": 0.0, "details": []}

    # Normalización: eliminar guiones, espacios y pasar a mayúsculas
    cif_clean = cif.replace("-", "").replace(" ", "").replace(".", "").upper()

    all_subsidies = []
    total_elements = 0

    try:
        for page_num in range(max_pages):
            params = {
                "vpd": "GE",           # Vista pública general
                "nifCif": cif_clean,
                "page": page_num,
                "pageSize": 50,
                "order": "fechaConcesion",
                "direccion": "desc",
            }

            response = requests.get(
                BDNS_API_URL,
                params=params,
                headers=HEADERS,
                timeout=20,
            )

            if response.status_code != 200:
                return {
                    "error": f"HTTP {response.status_code} al consultar BDNS",
                    "total_subsidies": 0,
                    "total_amount": 0.0,
                    "details": [],
                }

            data = response.json()
            content = data.get("content", [])

            # En la primera página obtenemos el total real
            if page_num == 0:
                total_elements = data.get("totalElements", 0)
                if total_elements == 0:
                    break

            for item in content:
                # El campo 'importe' es el importe bruto concedido
                importe = float(item.get("importe") or 0)

                # Organismo: usar nivel3 si existe, si no nivel2, si no nivel1
                organismo = (
                    item.get("nivel3")
                    or item.get("nivel2")
                    or item.get("nivel1")
                    or ""
                )

                all_subsidies.append({
                    "title": item.get("convocatoria", ""),
                    "amount": importe,
                    "date": item.get("fechaConcesion", ""),
                    "organism": organismo,
                    "instrument": item.get("instrumento", ""),
                    "url": item.get("urlBR", ""),
                    "code": item.get("codConcesion", ""),
                })

            # Si ya tenemos todos los registros, no paginamos más
            if data.get("last", True) or len(content) == 0:
                break

            # Pausa respetuosa entre páginas
            time.sleep(0.5)

    except requests.exceptions.Timeout:
        return {
            "error": "Timeout al conectar con la API de BDNS",
            "total_subsidies": 0,
            "total_amount": 0.0,
            "details": [],
        }
    except requests.exceptions.ConnectionError as exc:
        return {
            "error": f"Error de conexión con BDNS: {exc}",
            "total_subsidies": 0,
            "total_amount": 0.0,
            "details": [],
        }
    except Exception as exc:
        return {
            "error": str(exc),
            "total_subsidies": 0,
            "total_amount": 0.0,
            "details": [],
        }

    total_amount = sum(s["amount"] for s in all_subsidies)

    return {
        "total_subsidies": total_elements,          # Total real según la API
        "total_amount": total_amount,               # Suma de los importes paginados
        "details": all_subsidies,
    }
