# Reporte técnico de telemetría

Pipeline de análisis (`services/telemetry/analysis.py`) y endpoint `GET /telemetry/report`. Es un reporte **técnico**: salud del sistema, errores, tiempos de carga y fallos de login. No contiene métricas de negocio (ventas, conversión, ingresos); eso se construye más adelante con los pipelines de datos.

## Fórmula de cada métrica

`cargar (SQL) → refinar (Pandas) → convertir tipos → agrupar → agregar → servir`

- **Cargar:** el rango de `timestamp` (inicio inclusivo, fin exclusivo, UTC) y el `event_type` (`IN (...)`) se filtran en la consulta SQL. Solo se leen las columnas necesarias.
- **Refinar:** en Pandas se extraen las dimensiones de `tags` (por ejemplo `route_template`) y se descartan las filas con la dimensión o el valor nulos.
- **Convertir tipos:** `pd.to_datetime(..., utc=True)` antes de agrupar. El día (`YYYY-MM-DD`, UTC) se deriva del `datetime` ya convertido; así se evitan grupos incorrectos sin error visible.
- **Agrupar y agregar:** `groupby` + `.count()`, `.sum()`, `.mean()` y `.quantile(0.95)`. No hay bucles.
- **Servir:** lista de diccionarios con tipos nativos, serializable a JSON.

## Métricas

| Clave en `metrics` | Pregunta operacional | Eventos usados | Agrupación |
|---|---|---|---|
| `events_per_day` | ¿Qué eventos ocurren y con qué frecuencia? | todos | día y `event_type` |
| `error_rate_by_day` | ¿Qué tan sano está el sistema cada día? | todos (`level`) | día |
| `error_rate_by_type` | ¿Qué tipos de evento señalan problemas? | todos (`level`) | `event_type` |
| `page_load_ms_by_route` | ¿Qué tan rápido cargan las pantallas? | `page_load_measured` | día y ruta (`tags.route_template`) |
| `auth_failure_rate` | ¿Con qué frecuencia falla el inicio de sesión? | `login_failed`, `login_succeeded` | día |

Tasas: `error_rate = errores / eventos` (`level = error`); `problem_rate = (errores + avisos) / eventos` (`level` en `error` o `warn`). La tasa de fallos de login es `login_failed / (login_failed + login_succeeded)`.

## Endpoint

`GET /telemetry/report?start_date=...&end_date=...` (requiere inicio de sesión).

- Fechas ISO 8601. Sin parámetros: últimos 7 días (`end = ahora`, `start = ahora − 7 días`, UTC). El endpoint resuelve el período **una sola vez** y lo pasa a cada función; las funciones no aplican su propia ventana.
- Máximo 90 días. `start_date >= end_date` o más de 90 días: 422.
- **Caché en memoria de 60 s** por combinación de `start_date` y `end_date`. Sin parámetros la clave es `default`, de modo que la ventana por defecto, que se mueve con el reloj, también reutiliza el resultado. El pipeline no se ejecuta en cada petición.
- Respuesta: `{"period": {"from", "to"}, "metrics": {...}}`.

## Limitaciones

- La caché es por proceso: con varios workers cada uno tendría la suya.
- La latencia disponible es el tiempo de carga de pantalla (`page_load_measured`); el catálogo no emite `api_latency_recorded`.
- `login_failed` incluye los fallos de validación del formulario, además de las credenciales incorrectas.
