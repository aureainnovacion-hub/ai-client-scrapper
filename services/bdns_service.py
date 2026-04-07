import requests

def check_subsidies(cif):
    """
    Consulta la API de la BDNS (Hacienda) para verificar subvenciones concedidas a un CIF/NIF.
    """
    try:
        # Limpieza del CIF
        cif_limpio = cif.replace("-", "").replace(" ", "").upper()
        
        # Parámetros de la consulta (Hacienda API)
        params = {
            "vpd": "GE",
            "nifCif": cif_limpio,
            "page": 0,
            "pageSize": 50,
            "order": "fechaConcesion",
            "direccion": "desc"
        }
        
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
        
        response = requests.get(
            "https://www.pap.hacienda.gob.es/bdnstrans/api/concesiones/busqueda",
            params=params,
            timeout=15,
            headers=headers
        )
        
        # Si no hay contenido o error HTTP
        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}", "total_amount": 0, "details": []}
            
        data = response.json()
        
        subsidies = []
        for item in data.get("content", []):
            subsidies.append({
                "title": item.get("convocatoria", ""),
                "amount": item.get("importe", 0),
                "date": item.get("fechaConcesion", ""),
                "organism": item.get("nivel3", "") or item.get("nivel2", "")
            })
        
        return {
            "total_subsidies": data.get("totalElements", len(subsidies)),
            "total_amount": sum(s["amount"] for s in subsidies),
            "details": subsidies
        }
    except Exception as e:
        return {"error": str(e), "total_amount": 0, "details": []}
