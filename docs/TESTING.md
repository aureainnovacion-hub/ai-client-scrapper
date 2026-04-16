# Estrategia de Pruebas

Este documento describe la estrategia de pruebas del proyecto, los tipos de pruebas implementadas y cómo ejecutarlas.

## Pirámide de Pruebas

La estrategia de pruebas sigue el modelo de la pirámide de pruebas, priorizando las pruebas más rápidas y económicas en la base y reservando las más costosas para la cima.

| Nivel | Tipo | Velocidad | Coste | Cobertura |
|---|---|---|---|---|
| Base | Pruebas Unitarias | Muy rápida | Bajo | Alta |
| Medio | Pruebas de Integración | Media | Medio | Media |
| Cima | Pruebas E2E | Lenta | Alto | Baja |

## Tipos de Pruebas

### Pruebas Unitarias (`tests/unit/`)

Las pruebas unitarias verifican el comportamiento de unidades individuales de código (funciones, clases, módulos) de forma aislada. Se deben escribir para toda la lógica de negocio crítica. El objetivo es mantener una cobertura superior al 80%.

### Pruebas de Integración (`tests/integration/`)

Las pruebas de integración verifican la interacción entre múltiples componentes del sistema, como la integración con bases de datos, APIs externas o servicios internos. Se ejecutan en un entorno controlado con dependencias reales o simuladas (mocks/stubs).

### Pruebas End-to-End (`tests/e2e/`)

Las pruebas E2E simulan el comportamiento real de un usuario interactuando con el sistema completo. Se ejecutan contra un entorno de staging para validar los flujos de usuario más críticos antes de cada despliegue a producción.

## Ejecución de Pruebas

Las pruebas se ejecutan automáticamente en el pipeline de CI/CD en cada push y Pull Request. Para ejecutarlas localmente, consulte el archivo `README.md` del proyecto para los comandos específicos.

## Cobertura de Código

Los reportes de cobertura se generan automáticamente y se publican en Codecov. El pipeline fallará si la cobertura cae por debajo del umbral configurado. Revise el badge de cobertura en el `README.md` para conocer el estado actual.
