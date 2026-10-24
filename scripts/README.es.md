# Carpeta `scripts`

Esta carpeta contiene **scripts auxiliares** del monorepo: automatizaciones de desarrollo, utilidades de mantenimiento, tareas repetitivas (setup, lint, migraciones, generación de datos, etc.) y tooling interno.

- **Propósito principal**: agrupar herramientas de soporte que no pertenecen a una app/agente/pipeline específico, pero facilitan el trabajo del equipo.
- **Recomendación**: documenta cada script (qué hace, parámetros, requisitos, ejemplos de uso) y procura que sean reproducibles (y seguros) en distintos entornos.

## `analyze.py`

Valida y resume un CSV de incidencias de Brasaland, incluyendo desgloses por regla inválida, categoría, estado y satisfacción. No requiere dependencias externas.

```bash
python scripts/analyze.py scripts/incidents-brasaland.csv
```

El script solicita confirmación para exportar las métricas a `results.csv` en el directorio de trabajo actual.
