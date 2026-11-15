# Notas de la captura de telemetría en el frontend

Complementa `telemetry-plan.md` (plan aprobado) y `event-schemas.json`. Describe qué se implementó, dónde y en qué se aparta del plan y por qué.

## Cómo funciona

- `track(eventType, properties)` en `uis/backoffice/services/telemetry.ts` es la única vía de captura. Añade sola `eventId`, `timestamp`, `sessionId`, `userId`, `schemaVersion` y `requestId`.
- Cola en memoria → lote de hasta 20 eventos o cada 10 s → `POST` a `NEXT_PUBLIC_TELEMETRY_ENDPOINT`. Al esconder o cerrar la pestaña se envía lo pendiente con `navigator.sendBeacon`. Si el envío falla se reintenta hasta 3 veces con espera exponencial (1, 2 y 4 s) y después se descarta; un 4xx se descarta sin reintentar.
- Solo pasan las propiedades de la allowlist de cada evento (`lib/telemetry-allowlist.ts`, generada desde `event-schemas.json` y comprobada por un test). Un evento desconocido se descarta.
- El receptor es un stub (`POST /telemetry/events`): valida el formato, registra el recuento y el `event_type` y responde `{"received": N}`. No persiste nada.

## Eventos instrumentados (17 de 21)

| Evento | Grupo | Dónde se captura |
|---|---|---|
| `inbound_order_created` | obligatorio | `components/inventory-inbound-form.tsx` |
| `outbound_order_created` | obligatorio | `components/inventory-outbound-form.tsx` |
| `stock_waste_registered` | obligatorio | `components/inventory-outbound-form.tsx` |
| `stock_threshold_triggered` | obligatorio | `components/inventory-outbound-form.tsx` (vía `lib/inventory-telemetry.ts`) |
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

## Eventos no instrumentados y por qué

| Evento | Motivo |
|---|---|
| `direct_stock_edit_rejected` (obligatorio) | No existe ninguna pantalla ni endpoint que permita editar el stock directamente, así que no hay momento real que capturar (brecha B5 del plan). Se instrumentará cuando exista la guarda de backend |
| `ingredient_price_variance_detected` (obligatorio) | Las órdenes de entrada no guardan coste unitario (brecha B1), así que no hay variación que calcular |
| `product_created` | No hay pantalla de alta de producto en el backoffice |
| `api_latency_recorded` | El plan lo define como agregado por minuto de backend; ya existe el log `api.timing`. El rendimiento del frontend lo cubre `page_load_measured` |

## Desviaciones respecto al plan aprobado

- **`userId`**: el id de cuenta del sistema es un entero (claim `user_uuid` del token), no un UUID. Se corrigió el plan y el esquema: `userId` es el id en texto o `anonymous`.
- **Origen de los eventos de negocio**: el plan los asignaba al backend; este proyecto los captura en el frontend al confirmarse la respuesta del servidor (201). Cuando se implemente la persistencia, el backend podrá emitirlos con mayor fiabilidad.
- **`country`**: no existe un mapa local→país (brecha B3). Se usa el país del producto, y `currency` se deriva de él. En los datos semilla coincide con el local.
- **`reason` de la merma**: el formulario solo distinguía consumo y merma. Se añadió un selector de motivo (`expired`, `kitchen_error`, `theft_suspected`) que se envía solo a telemetría; la API de órdenes no lo guarda (brecha B2).
- **Umbral mínimo**: no existe en el servidor (brecha B4). `stock_threshold_triggered` usa el mismo umbral de "Stock bajo" que ya muestra la interfaz (20 para kg y litros, 50 para unidades) y se emite solo al cruzarlo hacia abajo.
- **`requestId`**: es un UUID por evento. La correlación real con los logs del backend (cabecera `X-Request-Id`) sigue pendiente (brecha B6).

## Privacidad

No se envían correos, contraseñas, nombres, títulos ni descripciones. Las rutas se envían como plantilla (`/inventory/products/{id}`), sin identificadores ni query string. Los errores de frontend llevan nombre y una huella hash, nunca el mensaje ni la traza.
