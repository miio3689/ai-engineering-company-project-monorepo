# Lógica compartida de Brasaland

Este paquete conserva sus tipos TypeScript en `types/` y aloja la lógica Python
en `python/brasaland_shared/`, sin mezclar ambos entornos. El módulo
`incidents.py` contiene la validación del CSV, los valores y etiquetas del
modelo de incidencias, las transiciones de estado y las transformaciones del
CSV al modelo.

Para importar el módulo Python desde el monorepo, se prepara `sys.path` con el
helper compartido y después se importa `brasaland_shared.incidents`:

```python
from services.api.shared_paths import ensure_shared_python_path

ensure_shared_python_path()

from brasaland_shared.incidents import validate_record, transform_csv_record
```

La API usa este patrón desde `services/api`; `scripts/seed_incidents.py` y
`scripts/analyze.py` añaden primero la raíz del monorepo a `sys.path`, lo que
permite ejecutarlos directamente desde la raíz. `scripts/analyze.py` mantiene
su interfaz pública como fachada compatible para los consumidores y pruebas
existentes.
