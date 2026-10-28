# Directorio de proveedores: almacenamiento y seed

Desde la **raíz del repositorio**, con [uv](https://docs.astral.sh/uv/)
instalado:

```bash
uv run seed
```

`uv` instala las dependencias del directorio en su entorno local y ejecuta
`services.api.seed:main`. No arranca el servidor ni cambia la API de incidencias.
La configuración Python de la raíz corresponde al comando de proveedores;
las instrucciones existentes de la API de incidencias siguen en [README.md](README.md).

## Persistencia

[database.py](database.py) abre TinyDB en `services/api/suppliers.json`, siempre
relativo al módulo y no al directorio desde el que se ejecuta Python. La tabla
se llama `suppliers`. El JSON local está excluido de Git.

[seed.py](seed.py) valida los 15 registros del briefing mediante
[Supplier](models.py), inserta solo los nombres que no existen y muestra el
número de registros insertados, omitidos y el total persistido. Si la base de
datos tiene solo algunos proveedores, completa los que faltan sin sobrescribir
tarifas, estados, notas ni fechas existentes.

TinyDB asigna cada identificador como `document.doc_id`; no se guarda un campo
`id` duplicado en el documento. `updated_at` se genera en UTC al insertar y se
almacena como texto ISO 8601 compatible con `SupplierResponse`.

Los imports son relativos al paquete: `from .models import Supplier` y
`from .database import get_suppliers_table`. Desde otros módulos se pueden usar
`from services.api.models import Supplier, SupplierResponse` y
`from services.api.database import get_suppliers_table`. No se necesita mover
archivos ni modificar `sys.path`.

El seeder también puede ejecutarse como módulo desde la raíz:

```bash
uv run python -m services.api.seed
```

Las ejecuciones del seeder deben ser secuenciales: TinyDB no ofrece garantías
para escrituras concurrentes de varios procesos.
