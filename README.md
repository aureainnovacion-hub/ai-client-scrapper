# AI Client Scrapper — Aurea Innovación

[![CI](https://github.com/aureainnovacion-hub/ai-client-scrapper/actions/workflows/ci.yml/badge.svg)](https://github.com/aureainnovacion-hub/ai-client-scrapper/actions)
[![CD](https://github.com/aureainnovacion-hub/ai-client-scrapper/actions/workflows/cd.yml/badge.svg)](https://github.com/aureainnovacion-hub/ai-client-scrapper/actions)

Bienvenido al repositorio oficial del **AI Client Scrapper** de Aurea Innovación. Este proyecto está estructurado según la plantilla corporativa para garantizar escalabilidad, seguridad y buenas prácticas desde el primer día.

## Índice

- [Inicio Rápido](#inicio-rápido)
- [Estructura del Repositorio](#estructura-del-repositorio)
- [Entornos](#entornos)
- [Seguridad](#seguridad)
- [CI/CD y Automatización](#cicd-y-automatización)
- [Pruebas](#pruebas)
- [Documentación](#documentación)
- [Contribución](#contribución)

---

## Inicio Rápido

Para levantar todo el entorno de desarrollo local (Scraper, Frontend Streamlit y Base de Datos) usando Docker:

```bash
git clone https://github.com/aureainnovacion-hub/ai-client-scrapper.git
cd ai-client-scrapper
make install
make dev
```

A continuación, complete los valores del archivo `.env` generado con su configuración SMTP y credenciales, y acceda a la interfaz web en `http://localhost:8501`.

---

## Estructura del Repositorio

La estructura de directorios está diseñada para ser clara, escalable y consistente entre proyectos de Aurea Innovación.

| Directorio / Archivo | Descripción |
|---|---|
| `apps/scraper/` | Lógica principal del scraper, validación de NIF y enriquecimiento BDNS (Python) |
| `apps/frontend/` | Interfaz de usuario (Streamlit) |
| `apps/database/` | Esquemas, migraciones y seeds de la base de datos |
| `docs/` | Documentación técnica (ADRs, API, Seguridad, Observabilidad) |
| `config/envs/` | Archivos de configuración por entorno |
| `deploy/` | Scripts y manifiestos de despliegue |
| `infrastructure/` | Código de infraestructura como código (IaC) |
| `scripts/` | Scripts de utilidad para desarrollo y mantenimiento |
| `tests/` | Pruebas automatizadas (unit, integration, e2e) |
| `.github/workflows/` | Pipelines de CI/CD con GitHub Actions |
| `docker-compose.yml` | Orquestación de contenedores para desarrollo local |
| `Makefile` | Automatización centralizada de tareas del proyecto |

---

## Entornos

El proyecto soporta tres entornos diferenciados. Consulte `docs/ENVIRONMENTS.md` para la guía completa de configuración.

| Entorno | Rama | Despliegue |
|---|---|---|
| Desarrollo | `feature/*`, `fix/*` | Manual / Local |
| Staging | `develop` | Automático en cada push |
| Producción | `main` | Automático con aprobación manual |

---

## Seguridad

La seguridad está integrada en cada fase del ciclo de desarrollo. Consulte `docs/SECURITY_GUIDE.md` para las directrices completas.

Para reportar una vulnerabilidad de seguridad, consulte `SECURITY.md`.

---

## CI/CD y Automatización

### GitHub Actions

Los pipelines están organizados por responsabilidad: build, tests, calidad, seguridad, despliegue a staging/producción, releases semánticos y notificaciones.

### Convenciones de Commits

Este repositorio sigue la especificación de [Conventional Commits](https://www.conventionalcommits.org/). Todos los mensajes de commit deben seguir el formato `tipo(ámbito): descripción` y son validados automáticamente.

---

## Pruebas

La estrategia de pruebas sigue la pirámide de testing. Consulte `docs/TESTING.md` para más detalles.

```bash
make test       # Ejecuta todas las pruebas
make test-unit  # Ejecuta pruebas unitarias
make test-e2e   # Ejecuta pruebas end-to-end
```

---

## Documentación

La documentación técnica del proyecto se encuentra en el directorio `docs/`:

- `docs/ARCHITECTURE.md` — Arquitectura del sistema y decisiones de diseño.
- `docs/adr/` — Registros de Decisiones de Arquitectura (Architecture Decision Records).
- `docs/OBSERVABILITY.md` — Guía de logging, métricas y trazas.
- `docs/RUNBOOK.md` — Procedimientos operacionales y respuesta a incidentes.
- `docs/ENVIRONMENTS.md` — Guía de configuración de entornos y secretos.
- `docs/SECURITY_GUIDE.md` — Directrices de seguridad.
- `docs/TESTING.md` — Estrategia y guía de pruebas.

---

## Contribución

Consulte `CONTRIBUTING.md` para las directrices de contribución y `CODE_OF_CONDUCT.md` para las normas de comportamiento en la comunidad.

## Licencia

Este proyecto está bajo la Licencia MIT - vea el archivo [LICENSE](LICENSE) para más detalles.
