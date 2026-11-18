# Notas de la captura de telemetría en el frontend

Complementa `telemetry-plan.md` (plan aprobado) y `event-schemas.json`. Describe qué se implementó, dónde y en qué se aparta del plan y por qué.

## Cómo funciona

- `track(eventType, properties)` en `uis/backoffice/services/telemetry.ts` es la única vía de captura. Añade sola `eventId`, `timestamp`, `sessionId`, `userId`, `schemaVersion` y `requestId`.
- Cola en memoria → lote de hasta 20 eventos o cada 10 s → `POST` a `NEXT_PUBLIC_TELEMETRY_ENDPOINT`. Al esconder o cerrar la pestaña se envía lo pendiente con `navigator.sendBeacon`. Si el envío falla se reintenta hasta 3 veces con espera exponencial (1, 2 y 4 s) y después se descarta; un 4xx se descarta sin reintentar.
- Solo pasan las propiedades de la allowlist de cada evento (`lib/telemetry-allowlist.ts`, generada desde `event-schemas.json` y comprobada por un test). Un evento desconocido se descarta.
- El receptor (`POST /telemetry/events`) valida cada evento, guarda los válidos en Supabase y responde `{"received": N, "stored": M, "rejected": R}` (ver `storage-notes.md`).

## Eventos instrumentados (19 de 21): las 6 obligatorias del BRIEFING y 13 identificados

| Evento | Grupo | Dónde se captura |
|---|---|---|
| `inbound_order_created` | obligatorio | `components/inventory-inbound-form.tsx` |
| `outbound_order_created` | obligatorio | `components/inventory-outbound-form.tsx` |
| `stock_waste_registered` | obligatorio | `components/inventory-outbound-form.tsx` |
| `stock_threshold_triggered` | obligatorio | `components/inventory-outbound-form.tsx` (vía `lib/inventory-telemetry.ts`) |
| `direct_stock_edit_rejected` | obligatorio | `components/stock-adjustment-attempt.tsx` (acción "Ajustar stock" de la tabla de productos) |
| `ingredient_price_variance_detected` | obligatorio | `components/inventory-inbound-form.tsx` (vía `lib/inventory-telemetry.ts`) |
| `outbound_order_rejected` | identificado | `components/inventory-outbound-form.tsx` |
| `inventory_form_validation_failed` | identificado | formularios de entrada y salida |
| `supplier_rate_changed` | identificado | `components/supplier-actions.tsx` |
| `incident_created` | identificado | `components/incident-register-form.tsx` |
| `login_succeeded`, `login_failed` | identificado | `hooks/use-auth-form.ts` |
| `password_changed` | identificado | `hooks/use-change-password.ts`, `hooks/use-reset-password.ts` |
| `session_expired`, `api_error_returned` | identificado | `services/api-client.ts` |
| `page_viewed`, `page_load_measured` | identificado | `components/telemetry-provider.tsx` |
| `frontend_error_captured` | identificado | `components/telemetry-provider.tsx` y `app/error.tsx` |
| `flow_abandoned` | identificado | `hooks/use-flow-abandonment.ts`, usado en 4 formularios |

## Cómo se cerraron las dos brechas de las obligatorias

- **Variación de precio (brecha B1 del plan).** Las órdenes de entrada ahora pueden guardar un coste unitario (`unit_cost`, opcional en la API para no romper clientes antiguos; el formulario lo exige). Una migración idempotente en `init_inventory_db` añade la columna a las tablas ya creadas. Al crear una entrada, el backend compara el coste nuevo con la media de las últimas 5 entradas con coste del mismo producto y proveedor y, si la variación supera el 10 % (en positivo o negativo), devuelve `price_variance` (`baseline_unit_cost`, `variance_pct`, `threshold_pct`) en la respuesta. El frontend emite `ingredient_price_variance_detected` y avisa al usuario. No se convierte moneda: el coste se guarda en la moneda del local.
- **Edición directa de stock (brecha B5 del plan).** Se añadió el endpoint guarda `PUT /inventory/products/{ingredient_id}/stock`, que siempre responde 403 con el mensaje "El stock no se modifica directamente: registra una orden de entrada o de salida." (la regla de negocio del BRIEFING) y registra el intento en el log del servidor. La tabla de productos ofrece la acción "Ajustar stock": el rechazo se muestra con enlaces a registrar una entrada o una salida, y el frontend emite `direct_stock_edit_rejected`. Esa acción es deliberadamente un intento que nunca prospera: sirve para formar al personal y para medir cuántas veces se intenta saltarse la trazabilidad.

## Eventos no instrumentados y por qué

| Evento | Motivo |
|---|---|
| `product_created` | No hay pantalla de alta de producto en el backoffice |
| `api_latency_recorded` | El plan lo define como agregado por minuto de backend; ya existe el log `api.timing`. El rendimiento del frontend lo cubre `page_load_measured` |

## Desviaciones respecto al plan aprobado

- **`userId`**: el id de cuenta del sistema es un entero (claim `user_uuid` del token), no un UUID. Se corrigió el plan y el esquema: `userId` es el id en texto o `anonymous`.
- **Origen de los eventos de negocio**: el plan los asignaba al backend; este proyecto los captura en el frontend al confirmarse la respuesta del servidor. La variación de precio la calcula el backend (donde está el histórico) y el frontend solo la emite. Cuando se implemente la persistencia, el backend podrá emitirlos con mayor fiabilidad.
- **`country`**: no existe un mapa local→país (brecha B3). Se usa el país del producto, y `currency` se deriva de él. En los datos semilla coincide con el local.
- **`reason` de la merma**: el formulario solo distinguía consumo y merma. Se añadió un selector de motivo (`expired`, `kitchen_error`, `theft_suspected`) que se envía solo a telemetría; la API de órdenes no lo guarda (brecha B2).
- **Umbral mínimo**: no existe en el servidor (brecha B4). `stock_threshold_triggered` usa el mismo umbral de "Stock bajo" que ya muestra la interfaz (20 para kg y litros, 50 para unidades) y se emite solo al cruzarlo hacia abajo.
- **`requestId`**: es un UUID por evento. La correlación real con los logs del backend (cabecera `X-Request-Id`) sigue pendiente (brecha B6).

## Privacidad

No se envían correos, contraseñas, nombres de personas, títulos ni descripciones. La única excepción es `supplier_name` (nombre comercial de la empresa proveedora, escrito por el usuario en el formulario de entrada), que el plan y el BRIEFING exigen para analizar las compras por proveedor. Las rutas se envían como plantilla (`/inventory/products/{id}`), sin identificadores ni query string. Los errores de frontend llevan nombre y una huella hash, nunca el mensaje ni la traza. El intento de edición directa envía solo el producto, el local y la cantidad intentada, no quién lo hizo más allá del `userId` del envelope.
