# Gestión de Entornos

Este documento describe la estrategia de entornos del proyecto y cómo configurarlos correctamente en GitHub.

## Entornos Definidos

El proyecto utiliza tres entornos diferenciados para gestionar el ciclo de vida del software de forma segura y controlada.

| Entorno | Rama | URL | Aprobación Manual | Descripción |
|---|---|---|---|---|
| `development` | `feature/*`, `fix/*` | localhost | No | Entorno local de cada desarrollador |
| `staging` | `develop` | staging.mi-proyecto.com | No | Pre-producción para QA y validación |
| `production` | `main` | mi-proyecto.com | **Sí** | Entorno productivo final |

## Configuración en GitHub

Para configurar los entornos en GitHub, navegue a **Settings > Environments** en su repositorio y cree los entornos `staging` y `production`.

### Entorno: staging

Configure los siguientes secretos y variables en el entorno `staging`:

| Nombre | Tipo | Descripción |
|---|---|---|
| `STAGING_DEPLOY_KEY` | Secreto | Clave SSH o token para el despliegue |
| `STAGING_DB_PASSWORD` | Secreto | Contraseña de la base de datos de staging |
| `STAGING_HOST` | Variable | Hostname del servidor de staging |

### Entorno: production

Configure los siguientes secretos y variables en el entorno `production`. Se recomienda activar la opción de **Required reviewers** para que al menos un responsable apruebe cada despliegue.

| Nombre | Tipo | Descripción |
|---|---|---|
| `PROD_DEPLOY_KEY` | Secreto | Clave SSH o token para el despliegue |
| `PROD_DB_PASSWORD` | Secreto | Contraseña de la base de datos de producción |
| `PROD_HOST` | Variable | Hostname del servidor de producción |

## Secretos a Nivel de Repositorio

Los siguientes secretos deben configurarse a nivel de repositorio (no de entorno) ya que son utilizados por múltiples workflows:

| Nombre | Descripción |
|---|---|
| `CODECOV_TOKEN` | Token para subir reportes de cobertura a Codecov |
| `SONAR_TOKEN` | Token de autenticación para SonarCloud |
| `DEPLOY_TOKEN` | Token genérico de despliegue (si aplica) |

## Estrategia de Ramas

El flujo de trabajo recomendado sigue el modelo **Gitflow**:

- `main`: Código en producción. Solo acepta merges desde `develop` o ramas `hotfix/*`.
- `develop`: Rama de integración. Recibe merges de ramas `feature/*` y `fix/*`.
- `feature/nombre-caracteristica`: Ramas de desarrollo de nuevas funcionalidades.
- `fix/nombre-corrección`: Ramas para corrección de errores no críticos.
- `hotfix/nombre-parche`: Ramas para correcciones urgentes en producción.
