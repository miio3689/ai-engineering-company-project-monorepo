# Optimización de rendimiento: caching

## 1. Resumen ejecutivo

- Se añadió una caché TTL en proceso para `GET /inventory/products` y `GET /inventory/orders`, con TTL de 60 segundos e invalidación tras escrituras de inventario confirmadas.
- En el volumen grande, un acierto bajó la media de productos de 81,64 ms a 6,12 ms (−92,51 %) y la de órdenes de 1.067,20 ms a 224,55 ms (−78,96 %) frente a la medición sin caché del mismo cambio.
- En el frontend se difirieron los resultados del análisis CSV y el editor de tarifas de proveedores; ambos quedan en chunks propios, pero el total comprimido aumentó 3.854 B gzip.
- Los dos chunks diferidos pesan en conjunto aproximadamente 1.915 B gzip. Ese es el ahorro máximo para quien no los usa, y es menor que el aumento total medido; el Lazy Loading funciona, pero no reduce el total transferido.
- En el listado de incidencias, el formateador de fecha se reutiliza como constante de módulo y las filas preparadas se memoizan con `useMemo([incidents])`.
- Un microbenchmark sintético de 5.000 fechas bajó de 284,087 ms a 16,446 ms al reutilizar el formateador; no es una medición de React en navegador.

## 2. Metodología y entorno de medición

### Instrumentación de la API

El middleware de [services/api/app/main.py](services/api/app/main.py) usa `time.perf_counter()` y registra en `api.timing` método, ruta, código HTTP y duración en milisegundos. Usa `request.url.path`, no la URL completa: no registra query string, cabeceras ni cuerpo. Los tests de [services/api/tests/test_timing_middleware.py](services/api/tests/test_timing_middleware.py) comprueban que no se filtran query string, `Authorization` ni cuerpo.

### Datos de carga

[services/api/seed_load.py](services/api/seed_load.py) genera datos para TinyDB y SQLite locales. El directorio predeterminado es `services/api/.loadtest`; el benchmark recibe `--output-dir`. [`.gitignore`](.gitignore) excluye `services/api/.loadtest/`. La ejecución descrita usa ficheros temporales locales; no se tocó Supabase.

Volúmenes informados para las ejecuciones:

| Volumen | Incidencias | Proveedores | Ingredientes | Entradas | Salidas |
|---|---:|---:|---:|---:|---:|
| Pequeño | 500 | 50 | 50 | 1.105 | 895 |
| Grande | 5.000 | 500 | 500 | 25.352 | 24.648 |

**Límite sobre esos conteos:** el benchmark solicita 2.000 o 50.000 movimientos. El seeder distribuye los movimientos y puede omitir salidas cuando no hay stock disponible en el local aleatorio; no fija una semilla. Por ello, las cantidades exactas de entradas/salidas anteriores son los conteos observados en la ejecución reportada, no resultados garantizados al repetirla.

### Medición de endpoints

[services/api/benchmark_endpoints.py](services/api/benchmark_endpoints.py) usa `TestClient`, descarta una llamada de calentamiento y mide al menos 30 llamadas por endpoint (`--calls` tiene un mínimo efectivo de 30). Las mediciones son seriales, con SQLite local y sin red a Supabase; no incluyen concurrencia. La latencia real con Supabase sería mayor y de otra naturaleza. El perfil del frontend no se hizo con React Profiler en navegador.

### Medición del bundle frontend

La comparación de bundle se hizo con [scripts/measure-chunks.mjs](scripts/measure-chunks.mjs), que suma el tamaño bruto y gzip de los archivos JS de `.next/static/chunks` y localiza en qué chunk aparece cada texto indicado. Antes/después:

| Medición total de JavaScript cliente | Antes | Después | Diferencia |
|---|---:|---:|---:|
| Archivos JS | 25 | 27 | +2 |
| Bytes brutos | 775.001 B | 784.563 B | +9.562 B |
| Gzip | 240.846 B | 244.700 B | +3.854 B (+1,6 %) |

Los tamaños gzip de los chunks diferidos individuales se midieron con `gzip` de línea de comandos; los totales, con `zlib` de Node. Son aproximados por la diferencia de método. La carga bajo interacción se comprobó en la pestaña Network según las pruebas manuales informadas; no se usó React Profiler. Los nombres de archivo de los chunks cambian en cada compilación, por lo que la comparación se hace por contenido y no por nombre.

## 3. Decisiones en el frontend

### Lazy Loading

Se difieren los dos componentes del backoffice que solo se presentan después de una acción del usuario:

| Componente | Condición de carga | Chunk diferido medido |
|---|---|---:|
| [incident-analysis-results.tsx](uis/backoffice/components/incident-analysis-results.tsx), cargado desde [incident-analysis-dashboard.tsx](uis/backoffice/components/incident-analysis-dashboard.tsx) mediante `next/dynamic` | Cuando existe `analysis`, es decir, después de analizar un fichero | `094z-oaatjind.js`: 3.590 B brutos / 1.235 B gzip |
| [supplier-rate-editor.tsx](uis/backoffice/components/supplier-rate-editor.tsx), cargado desde [supplier-actions.tsx](uis/backoffice/components/supplier-actions.tsx) mediante `next/dynamic` | Al pulsar «Editar tarifa» | `30e26vsldfm8p.js`: 1.143 B brutos / 680 B gzip |

No se usa `ssr: false`. Las cargas solo se activan al alcanzar sus condiciones. Los resultados conservan sus textos y estilos; ambos fallbacks tienen `role="status"`, y el fallback del análisis además `aria-busy` y altura reservada.

La suma de los dos chunks diferidos es aproximadamente **1.915 B gzip**. El total pasó de 240.846 B a 244.700 B gzip, mientras el chunk que contiene «Editar tarifa» pasó de 16.136 B brutos / 4.959 B gzip a 19.816 B brutos / 6.273 B gzip. Es decir, el aumento total medido (3.854 B) es mayor que lo que se difiere (unos 1,9 KB). Una explicación probable es que el cargador de `next/dynamic` y la nueva estructura de chunks añaden código, pero **esa causa no se verificó**; solo están medidos los números. Para quien no abre ninguno de los dos componentes, el ahorro potencial es de unos 1,9 KB gzip, y el balance total medido no compensa en bytes. Se aplicó por ser los únicos componentes condicionales identificados, no porque el bundle total haya mejorado.

Se descartaron:

- [create-candidate-form.tsx](uis/backoffice/components/create-candidate-form.tsx) y [candidate-detail-manager.tsx](uis/backoffice/components/candidate-detail-manager.tsx): forman parte del contenido inicial de sus rutas; diferirlos no retrasa su necesidad.
- [inventory-inbound-form.tsx](uis/backoffice/components/inventory-inbound-form.tsx) y [inventory-outbound-form.tsx](uis/backoffice/components/inventory-outbound-form.tsx): son el contenido principal de sus rutas.
- [incident-summary.tsx](uis/backoffice/components/incident-summary.tsx), [incident-list.tsx](uis/backoffice/components/incident-list.tsx), [inventory-products-table.tsx](uis/backoffice/components/inventory-products-table.tsx) y [supplier-directory.tsx](uis/backoffice/components/supplier-directory.tsx): contenido inicial de sus rutas, no paneles ocultos activados por interacción.

### Formateador y `useMemo` en `incident-list.tsx`

En [uis/backoffice/components/incident-list.tsx](uis/backoffice/components/incident-list.tsx), `displayDate` construía un `Intl.DateTimeFormat` por incidencia en cada render. El formateador ahora es una constante de módulo con las mismas opciones: locale `es-CO`, `dateStyle: "medium"` y `timeStyle: "short"`. No usa `useMemo`, ya que no depende de props ni de estado.

Las filas preparadas (incidencia y fecha formateada) usan `useMemo` con dependencias exactas **`[incidents]`**: el cálculo solo lee ese array; `displayDate` y el formateador son funciones/valores estables de módulo. Se mantiene «Fecha no disponible» para fechas inválidas y las mismas claves de lista.

Hay renders del componente aunque la lista no cambie: los estados `loading` y `error` del hook, y los estados locales `pendingIds` y `rowErrors`. Durante una actualización, el estado pendiente y el error pueden cambiar antes o después de que cambie `incidents`; en esos renders se reutiliza la preparación mientras conserva la identidad el array. La actualización optimista y la confirmación/reversión actualizan el array de forma inmutable y hacen que el memo recalcule cuando sí cambian sus datos.

Microbenchmark sintético en Node v24.22.2, mediana de tres ejecuciones, incluye parseo y `format()`:

| Filas | Formateador por fila | Formateador reutilizado |
|---:|---:|---:|
| 100 | 6,711 ms | 0,352 ms |
| 5.000 | 284,087 ms | 16,446 ms |
| 50.000 | 2.569,780 ms | 163,656 ms |

Es un benchmark de Node, no un perfil del navegador. El formateo de cada fecha sigue ocurriendo cuando cambia la lista. El beneficio del `useMemo` depende de cuántos renders ajenos a la lista ocurran; no se midió en navegador.

Pruebas frontend informadas: `npm run typecheck`, `npm run lint`, las 18 pruebas de auth, `npm run build` y comprobaciones manuales de `/suppliers`, `/incidents` y `/incidents/list`, todas correctas. El informe no afirma que esas pruebas manuales se hayan repetido durante la elaboración de este documento.

## 4. Decisiones en el backend

### Endpoints evaluados y línea base con volumen grande

| Endpoint | Media (ms) | p95 (ms) |
|---|---:|---:|
| `GET /api/incidents` | 54,48 | 73,76 |
| `GET /api/incidents` con filtros | 21,37 | 36,93 |
| `GET /api/incidents/summary` | 27,57 | 36,84 |
| `GET /suppliers` | 9,03 | 20,65 |
| `GET /inventory/products/1` | 11,12 | 11,96 |
| `GET /auth/me` | 2,89 | 3,28 |
| `GET /profiles/me` | 2,76 | 2,81 |
| `GET /users` | 2,76 | 2,82 |

### `GET /inventory/products`

La ruta calcula existencias agregando entradas y salidas y calcula existencias por local con consultas agrupadas. Su coste medido con volumen grande fue 81,64 ms sin caché tras el cambio y 6,12 ms en un acierto: **−92,51 %**, con n=30 en cada caso. Antes del cambio la media era 79,28 ms (p95 111,31 ms); el caso pequeño fue 13,43 ms antes, 11,94 ms sin caché y 3,45 ms con acierto (−71,13 %).

La frecuencia estimada a partir del frontend es una llamada al abrir la lista de productos y una al abrir cada formulario de entrada o salida; no hay polling. La estabilidad es razonable entre escrituras, y las altas/movimientos invalidan el resultado.

### `GET /inventory/orders`

La ruta consulta todas las entradas y salidas, compone y ordena una única lista. Con volumen grande: 1.122,12 ms antes del cambio (p95 1.255,79 ms), 1.067,20 ms sin caché tras el cambio y 224,55 ms con acierto: **−78,96 %** frente a la medición sin caché. Con volumen pequeño: 41,70 ms antes, 39,42 ms sin caché y 9,07 ms con acierto (−76,98 %). Las cifras son medias, n=30.

El historial se consulta al abrir la ruta, sin polling. La frecuencia prevista es una llamada por apertura del historial; las entradas y salidas invalidan la caché.

La capa sin caché tras el cambio se mantiene cerca de la línea base anterior en ambos endpoints; estas medidas no muestran un sobrecoste apreciable de la infraestructura de caché. La caché de órdenes aún tarda aproximadamente 225 ms con acierto porque FastAPI serializa de nuevo las 50.000 filas en cada respuesta. La paginación sería la solución de fondo y queda fuera de alcance.

### TTL, claves e invalidación

Ambos endpoints usan TTL de 60 segundos y claves `inventory.products` y `inventory.orders`, definidas en [services/api/routes/inventory.py](services/api/routes/inventory.py). La caché se invalida:

- `POST /inventory/products`: productos.
- `POST /inventory/orders/inbound` y `POST /inventory/orders/outbound`: productos y órdenes.

La invalidación ocurre después de `session.commit()` y antes de `session.refresh()`. No se cachean escrituras.

### Diseño de la caché

[services/api/cache.py](services/api/cache.py) implementa un diccionario en proceso protegido por `Lock`, expiración con `time.monotonic` y reloj inyectable para pruebas. Cada clave lleva un contador de generación: si una lectura empieza, luego se invalida la clave por una escritura y finalmente termina, la generación evita que esa lectura anterior vuelva a guardar un valor obsoleto. Si el loader falla, no se escribe un resultado en caché.

La autenticación se ejecuta como dependencia de FastAPI antes de la función de ruta y, por tanto, antes del `get_or_set`. La salida valida stock consultando la base de datos dentro de la propia ruta; nunca toma una decisión de negocio con el valor cacheado de la lista.

Es una caché por proceso. Los workers múltiples tendrían cachés independientes; el despliegue actual se reporta con un único proceso, aunque ese detalle de despliegue no se verificó en esta revisión. Escrituras externas a la API —por ejemplo scripts de seed o promoción de administrador— no invalidan estas claves y se reflejan al expirar el TTL. Redis sería una evolución natural si se necesitan varios workers o invalidación compartida.

## 5. Intercambios reconocidos

### Frescura frente a rendimiento

Se eligieron 60 segundos, no 300–600, como límite de obsolescencia para escrituras externas a la API, manteniendo útil la caché en periodos de lectura. Las escrituras hechas por las rutas invalidan de inmediato; solo una escritura externa podría dejar un listado obsoleto hasta la expiración, como máximo el TTL desde que se guardó esa entrada, salvo el tiempo de una solicitud que ya estuviera en curso.

Esto es aceptable para listados operativos porque la salida comprueba el stock actual contra la base de datos y el frontend vuelve a pedir el detalle tras cada movimiento. Ninguna decisión de negocio depende del valor cacheado del listado. No sería una estrategia adecuada para datos sensibles, decisiones transaccionales ni endpoints cuya respuesta deba reflejar inmediatamente escrituras hechas fuera del servicio.

Durante ráfagas de escrituras las entradas se invalidan con frecuencia y el beneficio cae; se espera más ganancia en periodos de lectura. El número real de aciertos en producción no se midió.

### Coste de Lazy Loading

La carga diferida evita pedir los dos componentes si el usuario no llega a abrir esas vistas, pero el total comprimido medido subió 3.854 B, más que los unos 1,9 KB que se difieren. La causa de ese aumento no se verificó (hipótesis: el cargador y la estructura de chunks). Por tanto, el Lazy Loading está comprobado funcionalmente, pero no constituye una mejora en el tamaño total del bundle.

## 6. Qué no se cacheó ni se optimizó y por qué

### Backend

- `GET /auth/me` y `GET /profiles/me`: datos personales; una clave compartida sin aislamiento por usuario podría filtrar datos. Además, su coste grande medido es de unos 3 ms.
- `GET /users`: datos de cuentas, sin consumidor frontend actual y coste grande de 2,76 ms.
- `GET /suppliers`: 9,03 ms en volumen grande; el frontend actualiza su estado local tras las escrituras.
- `GET /inventory/products/{id}`: 11,12 ms en volumen grande; el formulario de salida vuelve a solicitarlo tras cada movimiento para mostrar stock fresco.
- `GET /api/incidents/summary`: 27,57 ms para 5.000 incidencias, una llamada por vista y cambios con cada alta o actualización de estado; la ganancia esperada no compensa la invalidación adicional en esta iteración.
- `GET /api/incidents`, con y sin filtros: 54,48 ms y 21,37 ms de media; requeriría claves por filtro e invalidación al cambiar incidencias. Se descartó en esta iteración.
- No se cachean endpoints de escritura, `POST /api/incidents/analyze` ni la exportación CSV.

### Frontend

- `create-candidate-form`, `candidate-detail-manager` y los formularios de inventario son contenido principal de sus rutas, no paneles innecesarios de la carga inicial.
- En `inventory-orders-list`, el mapa de unidades se construye una vez al cargar; no se repite una búsqueda por clave dentro del render de cada orden.
- En `inventory-products-table` no se identificaron renders ajenos a los datos que justificaran `useMemo`.
- Se descartó `useMemo` para `incident-summary`, `incident-analysis-dashboard` y `supplier-directory`: los agregados o volúmenes de presentación son pequeños y no hay evidencia medida de un cálculo suficientemente caro.

## 7. Verificación

La suite de backend pasó de 126 a 131 tests con la cobertura del middleware de timing y a 143 con los tests de caché, según el historial de trabajo informado. Durante esta revisión se ejecutó:

```text
Ran 144 tests in 54.002s
OK
```

El test adicional de [services/api/tests/test_inventory_routes.py](services/api/tests/test_inventory_routes.py) fuerza `SQLAlchemyError` en el primer `Session.exec` de cada endpoint, verifica el 503 y luego una lectura 200 que vuelve a ejecutar SQL. Limpia la caché entre ambos casos. Los tests existentes cubren aciertos, expiración, invalidación, autenticación antes de una caché caliente, salida contra stock de base de datos y consultas.

Durante la revisión del loader de órdenes se había detectado que se perdía `.all()` en las dos consultas; ambas llamadas a `.all()` están presentes en el código actual. Esto conserva la ejecución dentro del `try`: los errores SQL se convierten en el 503 controlado y, al fallar el loader, no se cachea el resultado.

Las comprobaciones manuales frontend indicadas en la sección 3 se reportaron como correctas. No se repitió aquí la navegación en navegador.

## 8. Limitaciones y siguientes pasos

1. Migrar a Redis o caché compartida si se despliegan varios workers.
2. Paginar el historial de órdenes para evitar serializar 50.000 registros por respuesta.
3. Medir tasa de aciertos e invalidaciones en producción; actualmente no se midieron.
4. Perfilar React en un navegador real, además del microbenchmark de Node.
5. Repetir el benchmark contra Supabase real para incorporar latencia de red y comportamiento del servicio.
6. Verificar la causa del aumento de bytes del Lazy Loading (hipótesis del cargador y los chunks).
7. Se informaron 13 vulnerabilidades de `npm audit` en `uis/backoffice`; no se verificaron ni trataron por quedar fuera de alcance.

## 9. Cómo reproducir las mediciones

Desde la raíz del repositorio, el benchmark prepara los datos temporales, autentica un usuario de prueba y mide ambos volúmenes. Ejemplo:

```bash
JWT_SECRET_KEY=test-key-for-unit-tests-0123456789abcdef \
PYTHON_DOTENV_DISABLED=1 \
uv run --locked --group test python -m services.api.benchmark_endpoints \
  --output-dir services/api/.loadtest --calls 30 --volume both
```

Para un volumen individual, cambiar `--volume both` por `--volume small` o `--volume large`. El script descarta un calentamiento y ejecuta 30 llamadas medidas por endpoint; la medición de aciertos de caché se hace después de una serie que invalida la clave antes de cada llamada.

El seeder también puede ejecutarse por separado:

```bash
JWT_SECRET_KEY=test-key-for-unit-tests-0123456789abcdef \
PYTHON_DOTENV_DISABLED=1 \
uv run --locked --group test python -m services.api.seed_load \
  --output-dir services/api/.loadtest --incidents 500 --ingredients 50 \
  --movements 2000 --suppliers 50
```

Para el volumen grande, usar `--incidents 5000 --ingredients 500 --movements 50000 --suppliers 500`. El seeder es aleatorio, así que los conteos exactos de entradas y salidas pueden variar entre ejecuciones.

La medición del bundle usa el script [scripts/measure-chunks.mjs](scripts/measure-chunks.mjs), que se ejecuta desde `uis/backoffice` después de compilar:

```bash
cd uis/backoffice
npm run build
node ../../scripts/measure-chunks.mjs "Nueva tarifa" "Guardar tarifa" "Editar tarifa" "ndice de satisfacci" "requieren revisi"
```

El script imprime el número de archivos JS, el total bruto y gzip, los 8 chunks más grandes y el chunk donde aparece cada texto. Qué demuestra cada texto:

- «Nueva tarifa» y «Guardar tarifa» son textos del editor de tarifas diferido; deben aparecer en el mismo chunk (`30e26vsldfm8p.js` en la medición informada).
- «Editar tarifa» es el botón que se queda en el componente inicial; debe aparecer en un chunk distinto al del editor (`1tppo2234rfag.js` después del cambio y `0-9jcvkwrw2d7.js` antes).
- «ndice de satisfacci» y «requieren revisi» son textos del panel de resultados del análisis, diferido (`094z-oaatjind.js`).

Los textos están cortados para evitar las tildes, que pueden aparecer codificadas en el JavaScript compilado. Los nombres de archivo cambian en cada compilación: lo que debe comprobarse es qué textos comparten chunk, no los nombres.

### Commits de la rama

| Commit | Mensaje |
|---|---|
| [`6b2386a`](https://github.com/miio3689/ai-engineering-company-project-monorepo/commit/6b2386a) | Backend: análisis |
| [`c8761c5`](https://github.com/miio3689/ai-engineering-company-project-monorepo/commit/c8761c5) | Backend: caché e inventario |
| [`90ca654`](https://github.com/miio3689/ai-engineering-company-project-monorepo/commit/90ca654) | Frontend: Lazy Loading y useMemo |
