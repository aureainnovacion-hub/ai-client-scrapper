# Workflows de GitHub Actions

Esta carpeta contiene los workflows de GitHub Actions como archivos de referencia.

## Instrucciones de Instalación

Para activar los workflows en su proyecto, copie los archivos `.txt` de esta carpeta
a `.github/workflows/` renombrándolos con extensión `.yml`.

Por ejemplo:
```bash
mkdir -p .github/workflows
cp workflows_backup/workflows_ci.yml.txt .github/workflows/ci.yml
cp workflows_backup/workflows_cd.yml.txt .github/workflows/cd.yml
# ... y así sucesivamente para cada workflow
```

## Workflows Disponibles

| Archivo | Descripción |
|---|---|
| `workflows_ci.yml.txt` | Integración Continua: build, lint y pruebas |
| `workflows_cd.yml.txt` | Despliegue Continuo genérico |
| `workflows_tests.yml.txt` | Pruebas unitarias, integración y E2E con cobertura |
| `workflows_security-scan.yml.txt` | Seguridad: CodeQL, Gitleaks, Dependency Review |
| `workflows_deploy-staging.yml.txt` | Despliegue automático a staging (rama develop) |
| `workflows_deploy-production.yml.txt` | Despliegue a producción con aprobación manual |
| `workflows_release.yml.txt` | Creación automática de releases desde tags |
| `workflows_notifications.yml.txt` | Notificaciones a Google Chat tras despliegues |
