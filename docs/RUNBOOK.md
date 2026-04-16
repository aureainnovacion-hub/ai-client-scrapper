# Runbook Operacional

Este documento contiene los procedimientos estándar para operar el sistema en producción y responder a incidentes.

## 1. Despliegues

### Despliegue Estándar
El despliegue a producción es automático al hacer merge en `main`, pero requiere aprobación manual en la interfaz de GitHub Actions.

1. Crear Release tag (`vX.Y.Z`).
2. Aprobar el workflow en GitHub Actions > "Despliegue a Producción".
3. Verificar estado en Datadog / Grafana durante 15 minutos.

### Rollback (Vuelta Atrás)
Si el despliegue falla o introduce un bug crítico:

1. Identificar el commit estable anterior.
2. Ejecutar `git revert <commit-fallido>`.
3. Hacer push a `main`.
4. Aprobar el nuevo despliegue.

## 2. Respuesta a Incidentes (Incidents)

### 2.1. Base de Datos Caída o Saturada
**Síntomas:** Latencia alta (>1s), errores 500 masivos, alertas de CPU de DB al 100%.

**Acciones Inmediatas:**
1. Escalar verticalmente la instancia de base de datos si es posible.
2. Identificar consultas lentas (Slow Queries) en el panel de monitoreo.
3. Matar conexiones o consultas bloqueantes (`pg_cancel_backend(pid)`).
4. Si es un pico de tráfico legítimo, habilitar el "Modo Degradado" en la API.

### 2.2. Caída del Servicio de Caché (Redis)
**Síntomas:** Aumento repentino de la latencia y carga en la base de datos principal.

**Acciones Inmediatas:**
1. Reiniciar el servicio de Redis.
2. Si no se recupera, la aplicación está diseñada para fallar graciosamente (Graceful Degradation) y consultar directamente la DB. Monitorizar la DB de cerca.

### 2.3. Ataque de Denegación de Servicio (DDoS)
**Síntomas:** Tráfico anómalo masivo desde múltiples IPs, agotamiento de recursos.

**Acciones Inmediatas:**
1. Activar reglas estrictas en el WAF (Web Application Firewall) o Cloudflare.
2. Limitar el Rate Limiting a nivel de API Gateway a 10 req/s por IP.
3. Escalar horizontalmente el backend.

## 3. Mantenimiento Rutinario

### Copias de Seguridad (Backups)
- **Frecuencia:** Diaria a las 03:00 UTC.
- **Retención:** 30 días.
- **Restauración:** Ejecutar el script `scripts/restore-db.sh <fecha>`. Se debe probar la restauración al menos una vez al trimestre en el entorno de staging.

### Rotación de Certificados y Secretos
- Los certificados SSL/TLS se renuevan automáticamente vía Let's Encrypt 30 días antes de expirar.
- Los secretos de la base de datos deben rotarse manualmente cada 90 días.
