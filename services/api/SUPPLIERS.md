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

## API del directorio

Desde la raiz del repositorio:

```bash
uv run uvicorn services.api.app.main:app --host 0.0.0.0 --port 8000
```

El router se monta en la API existente sin cambiar los endpoints de incidencias.
Los cuerpos de peticion y las respuestas se documentan en `/docs`.

| Metodo | Ruta | Resultado |
| --- | --- | --- |
| POST | `/suppliers` | Crea con `Supplier`; devuelve 201, `id` y `updated_at` UTC |
| GET | `/suppliers` | Lista; filtros exactos opcionales `country` y `category`, combinados con AND |
| GET | `/suppliers/{id}` | Detalle o 404 |
| PATCH | `/suppliers/{id}/rate` | JSON `{"rate_per_unit": 29000}`; actualiza tarifa y fecha |
| PATCH | `/suppliers/{id}/status` | JSON `{"status": "suspended"}`; conserva la fecha de tarifa |
| DELETE | `/suppliers/{id}` | Elimina para corregir datos erroneos; devuelve 204 sin cuerpo |

Los PATCH rechazan campos adicionales, incluido `updated_at`, con 422.
El flujo habitual es suspender proveedores, no eliminarlos.
Los IDs inexistentes devuelven 404. Los filtros sin coincidencias devuelven `[]`.

Las operaciones del router se serializan dentro de un proceso para evitar
escrituras TinyDB simultaneas desde los hilos de FastAPI. Ejecutar con un solo
worker y no ejecutar el seeder mientras la API escribe.

La configuracion CORS existente no se ha modificado: solo permite GET, POST y
OPTIONS. PATCH y DELETE desde navegadores en otro origen requieren ampliar esa
configuracion en una tarea posterior.

Pruebas aisladas (usan una base temporal, no la base local):

```bash
uv run --group test python -m unittest discover -s services/api/tests -v
```
