# Observabilidad y Logging

Este documento define los estándares de observabilidad del proyecto, siguiendo las mejores prácticas de **OpenTelemetry**. Un sistema observable debe proporcionar visibilidad completa sobre su estado interno a través de tres pilares: Logs, Métricas y Trazas.

## 1. Logs Estructurados

Todos los logs de la aplicación deben emitirse en formato **JSON** estructurado, nunca como texto plano. Esto permite su ingestión y análisis automático en herramientas como ELK (Elasticsearch, Logstash, Kibana), Datadog o Splunk.

### Estructura Base del Log

```json
{
  "timestamp": "2026-04-13T10:00:00Z",
  "level": "INFO",
  "service": "plantilla-backend",
  "environment": "production",
  "trace_id": "5b8aa5a2d2c8684fa065d628",
  "message": "Usuario autenticado exitosamente",
  "user_id": "12345",
  "latency_ms": 45
}
```

### Niveles de Severidad

- `FATAL`: El sistema no puede continuar (ej. Base de datos caída). Dispara alertas inmediatas.
- `ERROR`: Una operación falló pero el sistema sigue vivo.
- `WARN`: Situación anómala pero recuperable (ej. Retries, límite de rate cercano).
- `INFO`: Hitos importantes del ciclo de vida de la aplicación.
- `DEBUG`: Información detallada para diagnóstico (desactivado en producción).

## 2. Trazas Distribuidas (Distributed Tracing)

Para entender el recorrido de una petición a través de múltiples servicios, bases de datos y colas, implementamos trazas distribuidas.

- Cada petición entrante debe generar o heredar un `trace_id`.
- El `trace_id` debe inyectarse automáticamente en:
  1. Todos los logs generados durante esa petición.
  2. Todas las cabeceras HTTP de peticiones salientes (propagación de contexto).
  3. Las respuestas de error hacia el cliente (para facilitar el reporte de bugs).

## 3. Métricas (Metrics)

El sistema debe exponer un endpoint (típicamente `/metrics` en formato Prometheus) con los siguientes indicadores RED (Rate, Errors, Duration):

1. **Tasa (Rate):** Peticiones por segundo recibidas.
2. **Errores (Errors):** Porcentaje de peticiones fallidas (códigos 5xx).
3. **Duración (Duration):** Tiempo de respuesta (percentiles p50, p90, p99).

Adicionalmente, se deben monitorizar métricas de infraestructura:
- Uso de CPU y Memoria.
- Conexiones activas a la base de datos.
- Tamaño de colas pendientes.

## 4. Alertas y SLAs

Las alertas no deben basarse en umbrales estáticos de CPU, sino en el impacto al usuario (SLIs).

**Ejemplos de alertas críticas:**
- Tasa de errores HTTP 5xx > 1% durante 5 minutos.
- Latencia p99 > 500ms durante 10 minutos.
- Consumo de conexiones a DB > 80%.
