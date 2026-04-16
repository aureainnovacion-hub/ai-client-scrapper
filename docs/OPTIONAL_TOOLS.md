# Herramientas Opcionales

Este documento describe herramientas avanzadas que **no están activadas por defecto** en la plantilla, pero que pueden incorporarse cuando el proyecto lo justifique. Cada herramienta incluye el criterio de adopción recomendado y las instrucciones de activación.

---

## Análisis de Calidad de Código

### SonarCloud (SaaS) o SonarQube (Self-hosted)

**Cuándo usarlo:** Proyectos con equipo de desarrollo, clientes o requisitos de auditoría de calidad continua.

SonarCloud analiza el código en busca de bugs, vulnerabilidades, code smells y duplicaciones. Para proyectos privados requiere licencia de pago. La alternativa self-hosted es SonarQube Community Edition (gratuita).

**Activación:**

1. Crear cuenta en [sonarcloud.io](https://sonarcloud.io) y vincular el repositorio.
2. Obtener el `SONAR_TOKEN` y añadirlo como secreto en GitHub.
3. Crear `sonar-project.properties` en la raíz:

```properties
sonar.projectKey=ORGANIZACIÓN_PROYECTO
sonar.organization=ORGANIZACIÓN
sonar.sources=apps/frontend/src,apps/backend/src
sonar.tests=tests
sonar.javascript.lcov.reportPaths=coverage/lcov.info
```

4. Añadir el workflow `code-quality.yml` a `.github/workflows/`:

```yaml
name: Calidad de Código
on:
  push:
    branches: [ "main", "develop" ]
  pull_request:
    branches: [ "main", "develop" ]
jobs:
  sonarcloud:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: SonarCloud Scan
        uses: SonarSource/sonarcloud-github-action@master
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
```

---

## Cobertura de Tests

### Codecov

**Cuándo usarlo:** Proyectos open source o con requisito de badge de cobertura público.

Para proyectos privados, Codecov tiene un plan de pago. Una alternativa gratuita es publicar el reporte como artefacto de GitHub Actions (ya incluido en `tests.yml`) o usar **Coveralls**.

**Activación:**

1. Crear cuenta en [codecov.io](https://codecov.io) y vincular el repositorio.
2. Obtener el `CODECOV_TOKEN` y añadirlo como secreto en GitHub.
3. Añadir al workflow de tests:

```yaml
- name: Subir cobertura a Codecov
  uses: codecov/codecov-action@v4
  with:
    token: ${{ secrets.CODECOV_TOKEN }}
    files: ./coverage.xml
    fail_ci_if_error: false
```

4. Añadir el badge al `README.md`:

```markdown
![Coverage](https://img.shields.io/codecov/c/github/ORGANIZACIÓN/PROYECTO)
```

---

## Rendimiento y Accesibilidad Web

### Lighthouse CI

**Cuándo usarlo:** Proyectos web con requisitos de rendimiento, accesibilidad o SEO.

La configuración base ya está en `apps/frontend/lighthouserc.js`. Para activarla en el pipeline:

1. Añadir el workflow de Lighthouse a `.github/workflows/lighthouse.yml`:

```yaml
name: Lighthouse CI
on:
  pull_request:
    paths:
      - 'apps/frontend/**'
jobs:
  lighthouse:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Lighthouse CI
        uses: treosh/lighthouse-ci-action@v11
        with:
          configPath: apps/frontend/lighthouserc.js
          uploadArtifacts: true
```

---

## Gestión de Dependencias Avanzada

### Renovate

**Cuándo usarlo:** Como alternativa a Dependabot cuando se necesita mayor control sobre las actualizaciones (agrupación de PRs, horarios personalizados, auto-merge selectivo).

Instalar la [GitHub App de Renovate](https://github.com/apps/renovate) y crear `renovate.json` en la raíz:

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:recommended"],
  "automerge": true,
  "automergeType": "pr",
  "packageRules": [
    {
      "matchUpdateTypes": ["patch", "minor"],
      "automerge": true
    },
    {
      "matchUpdateTypes": ["major"],
      "automerge": false,
      "labels": ["major-update"]
    }
  ]
}
```

---

## Observabilidad Avanzada

### OpenTelemetry + Grafana Stack

**Cuándo usarlo:** Servicios en producción con SLA, múltiples microservicios o requisitos de trazabilidad distribuida.

La guía completa de implementación está en `docs/OBSERVABILITY.md`. El stack recomendado es:

- **Logs:** Loki + Grafana
- **Métricas:** Prometheus + Grafana
- **Trazas:** Tempo + Grafana

Para entornos cloud, las alternativas gestionadas son Datadog, New Relic o AWS CloudWatch.
