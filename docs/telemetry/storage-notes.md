# Almacenamiento de eventos de telemetría

El stub `POST /telemetry/events` es ahora el receptor real: valida cada evento, guarda los válidos en Supabase y reporta qué se guardó y qué se rechazó. El frontend no cambió: la URL es la misma y el `TelemetryService` solo mira el código HTTP.

## Tabla `telemetry_events` (`services/api/sql/telemetry_events.sql`)

| Columna | Tipo | Origen |
|---|---|---|
| `id` | `uuid` clave primaria, default `gen_random_uuid()` | `eventId` (así un reintento del mismo lote no duplica filas) |
| `timestamp` | `timestamptz` obligatorio | `timestamp` del evento (momento de captura) |
| `service` | `text` obligatorio | constante `backoffice` |
| `event_type` | `text` obligatorio | `event_type` |
| `level` | `text`, default `info` | `info`, `warn` o `error` según el tipo de evento |
| `value` | `numeric` | número principal copiado de `properties` |
| `message` | `text` | resumen legible |
| `tags` | `jsonb`, default `{}` | `properties` + `session_id`, `user_id`, `request_id`, `schema_version` |

Índices: `timestamp`, `event_type` y GIN sobre `tags`. El mapeo completo (qué nivel, qué valor y qué mensaje tiene cada evento) está en `telemetry-plan.md`, sección 11.

`tags` conserva **todas** las propiedades del allowlist, incluidas las dimensiones del BRIEFING (`location_id`, `country`, `product_id`, `product_category`, `quantity`, `unit`, `currency`, `reason`…), y además los identificadores del envelope. Ejemplo: `select * from telemetry_events where tags @> '{"country":"CO"}'` usa el índice GIN.

## Inmutabilidad y seguridad

- No existe ningún código de `UPDATE` ni `DELETE`. La tabla solo recibe `INSERT`.
- La tabla tiene `row level security` activado sin políticas: la API pública de Supabase no puede leerla ni escribirla; solo el backend, con su conexión directa.
- Para borrar datos de prueba, `truncate public.telemetry_events;` en el SQL Editor.

## Endpoint

1. Acepta `{"events": [...]}` de forma laxa (no tipa el cuerpo con `list[TelemetryEvent]`, para no devolver 422 al lote entero). Un cuerpo que no es JSON o sin lista `events` es 422; más de 100 eventos o 256 KB es 413.
2. Cada elemento se valida por separado con `TelemetryEvent.model_validate` (modelo sin cambios) y con el contrato de `event-schemas.json` (tipo de evento conocido, propiedades obligatorias, ninguna fuera del allowlist, enums y rangos). Una copia del contrato vive en `services/api/telemetry_schemas/` porque el contenedor solo lleva `services/`; un test la mantiene idéntica a `docs/telemetry/event-schemas.json`.
3. Los inválidos suman a `rejected` y el resto se guarda igual.
4. Los válidos se insertan con **un único `INSERT` multifila en una sola transacción**. Un reintento del mismo lote no duplica filas (`ON CONFLICT (id) DO NOTHING`).
5. Responde `200 {"received": N, "stored": M, "rejected": R}`. Si la base de datos falla, responde 503 y no guarda nada (el `TelemetryService` reintenta).

El log (`api.telemetry`) muestra los recuentos y los `event_type`, nunca propiedades ni identificadores de usuario.
