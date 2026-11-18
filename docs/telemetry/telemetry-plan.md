# Plan de telemetría de Brasaland

Versión del plan: 1.0.0 · Versión de esquema de eventos: `1.0.0` · Estado: diseño (sin instrumentación)

## 1. Contexto y alcance

Brasaland opera 14 locales (Colombia y Florida) con un sistema de inventario en producción: backend FastAPI con autenticación, modelo relacional en Supabase y una regla innegociable: **el stock nunca se modifica directamente, solo mediante órdenes de entrada y salida trazables a un usuario**.

El sistema funciona, pero operaciones no puede responder preguntas básicas (órdenes por día, errores de validación por producto, intentos de saltarse el control, alertas de stock mínimo) ni sobre el resto del backoffice (login, navegación, flujos abandonados, rendimiento, errores). Este documento responde al RFI: es el catálogo de datos que vale la pena capturar, su diseño y su estrategia de entrega. **No incluye código ni instrumentación.**

Cómo se leyó el sistema: el plan se basa en el código existente (`services/api/routes/inventory.py`, `services/api/inventory/models.py`, `services/api/routes/auth.py`, `services/api/app/main.py` y las 18 rutas de `uis/backoffice/app`) y en el `BRIEFING` de la compañía. Todo lo que se afirma del sistema actual se puede verificar en esos archivos.

Convenciones:

- Todos los eventos siguen la taxonomía `entidad_acción` en minúsculas con guion bajo.
- Las fechas son ISO 8601 en UTC. Los importes se registran en la moneda del local (`COP` o `USD`); **la telemetría nunca convierte monedas**.
- El idioma de la interfaz (español/inglés) es independiente de `country` y no genera eventos de inventario.
- Ningún evento contiene nombres de empleados, datos de clientes ni texto libre.

## 2. Métricas obligatorias del BRIEFING

Son el piso del plan. Se reproducen tal como las define el BRIEFING y entran todas en el catálogo con el grupo `obligatorio`.

| `event_type` | Se dispara cuando... | Decisión que habilita |
|---|---|---|
| `inbound_order_created` | Un local registra la llegada de mercancía de un proveedor | Consolidar compras entre locales para negociar mejores precios (Lucía) |
| `outbound_order_created` | Un local registra consumo de ingredientes en la preparación de un plato | Ajustar la sugerencia automática de pedidos a proveedores (Felipe) |
| `stock_waste_registered` | Un local registra merma (vencido, error de cocina, pérdida/robo) | Priorizar auditorías de merma en los locales con peor indicador (Felipe) |
| `stock_threshold_triggered` | El stock cae por debajo del mínimo configurado para ese local | Ajustar el umbral mínimo o la frecuencia de reabastecimiento |
| `direct_stock_edit_rejected` | Un usuario intenta modificar el stock fuera de una orden y el sistema lo rechaza | Reforzar capacitación o permisos donde ocurre más (Jake) |
| `ingredient_price_variance_detected` | El costo unitario de una entrada varía más de un umbral (10 %) respecto al histórico producto/proveedor | Alertar a Lucía y Mariana para renegociar o buscar proveedor alterno |

Campos mínimos en `properties` de los eventos de inventario: `location_id`, `country`, `product_id`, `product_category`, `quantity`, `unit`, `currency`; y `reason` solo para merma (`expired`, `kitchen_error`, `theft_suspected`).

## 3. Flujo de inventario y puntos de instrumentación

Flujo: el operador inicia sesión → entra en `/inventory` → consulta productos (`/inventory/products`) → abre el formulario de entrada o de salida → el frontend valida → la API valida stock y guarda → el sistema evalúa umbrales y precios → el operador ve el resultado.

Se identifican **9 puntos de instrumentación** en ese flujo:

| # | Punto | Dónde ocurre | Eventos que alimenta |
|---|---|---|---|
| P1 | Acceso y consulta de pantallas de inventario | `uis/backoffice/app/inventory/**/page.tsx`; `GET /inventory/products` y `GET /inventory/orders` | `page_viewed`, `page_load_measured` |
| P2 | Validación fallida en formularios de entrada/salida | `uis/backoffice/components/inventory-inbound-form.tsx`, `inventory-outbound-form.tsx` (validación cliente y respuesta 422) | `inventory_form_validation_failed` |
| P3 | Orden de entrada guardada | `create_inbound_order` en `services/api/routes/inventory.py` (`POST /inventory/orders/inbound`), tras `session.commit()` | `inbound_order_created`, `ingredient_price_variance_detected` |
| P4 | Orden de salida guardada (consumo o merma) | `create_outbound_order` (`POST /inventory/orders/outbound`), tras `session.commit()`; el campo `IngredientExit.reason` distingue `consumption` y `waste` | `outbound_order_created`, `stock_waste_registered`, `stock_threshold_triggered` |
| P5 | Orden de salida rechazada | `create_outbound_order`: 400 por stock insuficiente y 404 por ingrediente inexistente | `outbound_order_rejected` |
| P6 | Intento de modificar stock directamente | **No existe endpoint hoy**; se diseña como guarda en la API sobre cualquier intento de modificar stock fuera de una orden | `direct_stock_edit_rejected` |
| P7 | Fallo de base de datos | `_database_error` en `inventory.py` (503 y 409) | `api_error_returned` |
| P8 | Alta de producto | `create_product` (`POST /inventory/products`) | `product_created` |
| P9 | Abandono del formulario | Salida de la ruta con formulario iniciado y sin enviar | `flow_abandoned` |

## 4. Catálogo completo de eventos

Total: **21 eventos** = **6 obligatorios** (BRIEFING) + **15 oportunidades identificadas** (propuestas por nosotros), en **5 categorías** (negocio, autenticación, rendimiento, errores, navegación).

La columna "Viabilidad" indica si los datos existen hoy o qué falta (detalle en la sección 5).

| `event_type` | Categoría | Grupo | Dónde ocurre | Viabilidad |
|---|---|---|---|---|
| `inbound_order_created` | negocio (inventario) | obligatorio | `create_inbound_order`, `routes/inventory.py` | Lista (el coste requiere cambio de modelo) |
| `outbound_order_created` | negocio (inventario) | obligatorio | `create_outbound_order`, con `reason = consumption` | Lista |
| `stock_waste_registered` | negocio (inventario) | obligatorio | `create_outbound_order`, con `reason = waste` | Requiere motivos de merma nuevos (brecha B2) |
| `stock_threshold_triggered` | negocio (inventario) | obligatorio | Tras el commit de una salida, evaluando el stock del local | Requiere umbral por local (B4) |
| `direct_stock_edit_rejected` | negocio (inventario) | obligatorio | Guarda sobre edición directa de stock | Requiere guarda nueva (B5) |
| `ingredient_price_variance_detected` | negocio (inventario) | obligatorio | Tras el commit de una entrada | Requiere coste unitario en entradas (B1) |
| `outbound_order_rejected` | negocio (inventario) | oportunidad | `create_outbound_order`, ramas 400 y 404 | Lista |
| `product_created` | negocio (inventario) | oportunidad | `create_product` | Lista |
| `inventory_form_validation_failed` | negocio (inventario) | oportunidad | Formularios de entrada, salida y producto (frontend) | Frontend nuevo |
| `supplier_rate_changed` | negocio (proveedores) | oportunidad | `PATCH /suppliers/{id}/rate`, `routes/suppliers.py` | Lista |
| `incident_created` | negocio (incidencias) | oportunidad | `POST /api/incidents`, `routes/incidents.py` | Lista |
| `login_succeeded` | autenticación | oportunidad | `POST /auth/login`, `routes/auth.py` | Lista |
| `login_failed` | autenticación | oportunidad | `POST /auth/login` (rama de error) | Lista |
| `session_expired` | autenticación | oportunidad | Frontend, al recibir 401 con sesión previa | Frontend nuevo |
| `password_changed` | autenticación | oportunidad | `POST /auth/change-password` y `POST /auth/reset-password` | Lista |
| `api_latency_recorded` | rendimiento | oportunidad | Middleware `api.timing` de `app/main.py` (ya mide por petición) | Lista (agregación nueva) |
| `page_load_measured` | rendimiento | oportunidad | Frontend, cada navegación | Frontend nuevo |
| `api_error_returned` | errores | oportunidad | Respuestas 5xx de la API, incluido `_database_error` | Lista |
| `frontend_error_captured` | errores | oportunidad | Error boundary y errores no capturados del navegador | Frontend nuevo |
| `page_viewed` | navegación | oportunidad | Cambio de ruta en `uis/backoffice` | Frontend nuevo |
| `flow_abandoned` | navegación | oportunidad | Formularios de entrada, salida, incidencia y proveedor | Frontend nuevo |

### 4.1 Hipótesis y decisión de cada evento

Cada evento completa la frase: "Capturamos `[event_type]` porque necesitamos saber `[hipótesis]`, lo que nos permite tomar la decisión `[decisión]`."

**Obligatorios**

1. Capturamos `inbound_order_created` porque necesitamos saber cuánto y qué se compra, por local y por proveedor, lo que nos permite tomar la decisión de consolidar compras entre locales para negociar mejores precios.
2. Capturamos `outbound_order_created` porque necesitamos saber qué ingredientes se consumen y a qué ritmo por local, lo que nos permite tomar la decisión de ajustar la sugerencia automática de pedidos a proveedores.
3. Capturamos `stock_waste_registered` porque necesitamos saber cuánto producto se pierde, por qué razón y en qué local, lo que nos permite tomar la decisión de priorizar auditorías de merma en los locales con peor indicador.
4. Capturamos `stock_threshold_triggered` porque necesitamos saber con qué frecuencia un local se queda corto de un ingrediente clave, lo que nos permite tomar la decisión de ajustar el umbral mínimo o la frecuencia de reabastecimiento de ese producto.
5. Capturamos `direct_stock_edit_rejected` porque necesitamos saber si el personal intenta saltarse el control de trazabilidad, lo que nos permite tomar la decisión de reforzar capacitación o permisos en los locales con más intentos.
6. Capturamos `ingredient_price_variance_detected` porque necesitamos saber cuándo un ingrediente clave sube de precio de forma anómala, lo que nos permite tomar la decisión de alertar para renegociar o buscar un proveedor alterno.

**Oportunidades identificadas**

7. Capturamos `outbound_order_rejected` porque necesitamos saber con qué frecuencia el stock registrado no cubre lo que cocina dice haber usado, lo que nos permite tomar la decisión de programar un conteo físico en ese local y producto y revisar entradas olvidadas.
8. Capturamos `product_created` porque necesitamos saber cuántos productos nuevos se dan de alta y en qué categoría y país, lo que nos permite tomar la decisión de centralizar el alta del catálogo o limpiar duplicados.
9. Capturamos `inventory_form_validation_failed` porque necesitamos saber en qué campos fallan más los formularios de inventario, lo que nos permite tomar la decisión de rediseñar ese campo o capacitar a los locales.
10. Capturamos `supplier_rate_changed` porque necesitamos saber cuándo y cuánto cambian las tarifas de los proveedores, lo que nos permite tomar la decisión de cruzarlo con las variaciones de precio para renegociar o cambiar de proveedor.
11. Capturamos `incident_created` porque necesitamos saber cuántas incidencias se registran por categoría y en qué momentos, lo que nos permite tomar la decisión de reforzar la atención en las franjas y categorías con más incidencias.
12. Capturamos `login_succeeded` porque necesitamos saber cuántos operadores acceden por día y a qué horas, lo que nos permite tomar la decisión de dimensionar el soporte y programar mantenimientos fuera de las horas de uso.
13. Capturamos `login_failed` porque necesitamos saber cuántos intentos fallidos hay por día y por sesión, lo que nos permite tomar la decisión de bloquear posibles ataques de fuerza bruta y detectar usuarios con problemas de acceso.
14. Capturamos `session_expired` porque necesitamos saber con qué frecuencia caduca la sesión a mitad del trabajo, lo que nos permite tomar la decisión de ajustar la duración del token o añadir renovación.
15. Capturamos `password_changed` porque necesitamos saber cuántas contraseñas se cambian o restablecen y por qué vía, lo que nos permite tomar la decisión de simplificar el acceso o planificar campañas de seguridad.
16. Capturamos `api_latency_recorded` porque necesitamos saber qué endpoints son lentos y cómo evoluciona su latencia, lo que nos permite tomar la decisión de qué rutas optimizar o cachear primero.
17. Capturamos `page_load_measured` porque necesitamos saber cuánto tarda en cargar cada pantalla para el operador, lo que nos permite tomar la decisión de qué pantallas optimizar en el frontend.
18. Capturamos `api_error_returned` porque necesitamos saber cuántas respuestas 5xx se producen y en qué ruta, lo que nos permite tomar la decisión de alertar y escalar incidentes de disponibilidad.
19. Capturamos `frontend_error_captured` porque necesitamos saber qué errores no capturados ocurren y en qué pantalla, lo que nos permite tomar la decisión de priorizar correcciones por frecuencia.
20. Capturamos `page_viewed` porque necesitamos saber qué secciones visitan más los operadores, lo que nos permite tomar la decisión de qué secciones mejorar primero y cuáles reubicar o retirar.
21. Capturamos `flow_abandoned` porque necesitamos saber en qué paso se abandonan los formularios, lo que nos permite tomar la decisión de simplificar ese flujo.

## 5. Brechas entre el BRIEFING y el sistema actual

Comprobadas leyendo el código. Ninguna se corrige en este proyecto: solo se documentan.

| # | Brecha | Evidencia | Qué haría falta |
|---|---|---|---|
| B1 | Las entradas no guardan coste unitario ni moneda | `IngredientEntry` solo tiene cantidad, `supplier_name`, `location_id`, fecha y `user_uuid` | Añadir `unit_cost` a la entrada; la moneda se deriva del país del local |
| B2 | La merma no tiene motivo detallado | `IngredientExit.reason` solo admite `consumption` y `waste` (restricción de base de datos) | Ampliar a `expired`, `kitchen_error`, `theft_suspected` para las salidas de merma |
| B3 | No hay tabla de locales ni país por local | `location_id` es un entero de 1 a 14; `country` solo existe en `Ingredient` | Un mapa local→país (CO/US), de donde sale `country` y `currency` |
| B4 | No hay umbral mínimo por local en la API | No existe campo ni configuración; el frontend calcula un nivel con `getStockLevel` | Un umbral por producto y local, guardado en servidor |
| B5 | No existe edición directa de stock | `routes/inventory.py` no tiene ningún endpoint de ese tipo | Una guarda que rechace y registre cualquier intento de modificar stock fuera de una orden |
| B6 | No hay correlación entre frontend, backend y logs | No aparece `request_id`, `X-Request-Id` ni `sessionId` en ningún `.py`, `.ts` ni `.tsx` | Cabeceras `X-Request-Id` y `X-Session-Id` y su lectura en el middleware (también en la configuración CORS) |
| B7 | No hay canal ni almacén de eventos | Hoy solo existe el log `api.timing` | Un endpoint de ingestión para eventos del frontend y un destino de almacenamiento (proyectos posteriores) |
| B8 | Valores distintos para lo mismo | Proveedores usan país `Colombia`/`USA` y categorías en inglés; el BRIEFING usa `CO`/`US` | El plan fija `CO`/`US` y las categorías `meat`, `produce`, `sauce`, `beverage`, `packaging`, `cleaning`, con tabla de equivalencias |


## 6. Event Envelope

Todo evento, sin excepción, lleva este envelope. Los campos propios de cada evento van solo dentro de `properties`.

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `eventId` | UUID | Sí | Identificador único del evento; permite deduplicar reenvíos |
| `timestamp` | texto ISO 8601 en UTC | Sí | Momento en que ocurrió el hecho (no el de envío) |
| `sessionId` | UUID | Sí | Sesión del navegador; lo genera el frontend y viaja en `X-Session-Id` |
| `userId` | texto numérico o `anonymous` | Sí | Identificador interno de la cuenta: el mismo valor que el sistema ya guarda en las órdenes como `user_uuid`, que en el código real es un entero (por ejemplo `"42"`). Antes de iniciar sesión vale `anonymous` |
| `event_type` | texto `entidad_acción` | Sí | Tipo de evento; patrón `^[a-z]+(_[a-z]+)+$` |
| `schemaVersion` | texto `mayor.menor.parche` | Sí | Versión del esquema del evento; empieza en `1.0.0` |
| `requestId` | UUID o `none` | Sí | Correlación frontend–backend–logs (`X-Request-Id`). Vale `none` en eventos que no nacen de una petición concreta (agregados y métricas del navegador) |
| `properties` | objeto | Sí | Payload específico, limitado por la allowlist del evento |

Ejemplo:

```json
{
  "eventId": "7d1f6a52-3c0e-4b8a-9d2e-5f4c1a9b8e70",
  "timestamp": "2026-11-15T14:32:08.120Z",
  "sessionId": "0b9a3c4e-6d1f-4e2a-8c57-1f3e9a7b2d64",
  "userId": "42",
  "event_type": "inbound_order_created",
  "schemaVersion": "1.0.0",
  "requestId": "a41c5e77-2b9d-4f08-b3a6-8e0d7c2f1a55",
  "properties": {
    "location_id": 3,
    "country": "CO",
    "product_id": 12,
    "product_category": "meat",
    "quantity": 25.5,
    "unit": "kg",
    "currency": "COP",
    "inbound_order_id": 481,
    "supplier_name": "Proveedor Ejemplo"
  }
}
```

Reglas del envelope:

- El servidor es la fuente de verdad del `timestamp` en eventos de backend; el navegador usa su reloj solo en eventos de frontend.
- `eventId` se genera una sola vez por evento. Si un envío se reintenta, el `eventId` no cambia.
- La versión del esquema sube la parte menor al añadir propiedades opcionales y la mayor al cambiar o quitar una existente.
- La taxonomía es `entidad_acción` con verbos en participio o equivalentes coherentes: `_created`, `_rejected`, `_triggered`, `_registered`, `_detected`, `_changed`, `_viewed`, `_failed`, `_succeeded`, `_expired`, `_captured`, `_recorded`, `_measured`, `_abandoned`, `_returned`.

## 7. Esquemas y allowlists

La allowlist de cada evento es la lista cerrada de claves permitidas en `properties`. **Cualquier clave fuera de la lista se descarta y el evento se rechaza** (`additionalProperties: false` en `event-schemas.json`).

### 7.1 Diccionario de propiedades comunes

| Propiedad | Tipo y valores | Descripción |
|---|---|---|
| `location_id` | entero 1 a 14 | Local, igual que la restricción de base de datos |
| `country` | `CO` o `US` | País del **local** (derivado del mapa local→país, brecha B3). No depende del idioma de la interfaz |
| `currency` | `COP` o `USD` | Moneda del local; se deriva del país y no se convierte nunca |
| `product_id` | entero ≥ 1 | Identificador del ingrediente |
| `product_category` | `meat`, `produce`, `sauce`, `beverage`, `packaging`, `cleaning` | Categoría del ingrediente tal como la guarda el sistema |
| `quantity` | número ≥ 0 | Cantidad en la `unit` indicada |
| `unit` | `kg`, `litro`, `unidad` | Unidad del producto |
| `supplier_name` | texto 1 a 120 | Nombre comercial del proveedor (empresa, no persona) |
| `route_template` | texto que empieza por `/` | Ruta con parámetros sin sustituir, por ejemplo `/inventory/products/{ingredient_id}`. **Nunca la URL completa ni su query string** |

### 7.2 Allowlist por evento

Las propiedades obligatorias van en la columna 2; las opcionales, en la 3. Los siete campos mínimos del BRIEFING son `location_id`, `country`, `product_id`, `product_category`, `quantity`, `unit` y `currency`.

| `event_type` | Obligatorias | Opcionales |
|---|---|---|
| `inbound_order_created` | `location_id`, `country`, `product_id`, `product_category`, `quantity`, `unit`, `currency`, `inbound_order_id`, `supplier_name` | `unit_cost` |
| `outbound_order_created` | `location_id`, `country`, `product_id`, `product_category`, `quantity`, `unit`, `currency`, `outbound_order_id` | — |
| `stock_waste_registered` | `location_id`, `country`, `product_id`, `product_category`, `quantity`, `unit`, `currency`, `outbound_order_id`, `reason` | — |
| `stock_threshold_triggered` | `location_id`, `country`, `product_id`, `product_category`, `quantity`, `unit`, `currency`, `threshold_quantity`, `triggering_outbound_order_id` | — |
| `direct_stock_edit_rejected` | `location_id`, `country`, `product_id`, `product_category`, `quantity`, `unit`, `currency`, `attempted_operation`, `rejection_reason` | — |
| `ingredient_price_variance_detected` | `location_id`, `country`, `product_id`, `product_category`, `quantity`, `unit`, `currency`, `inbound_order_id`, `supplier_name`, `unit_cost`, `baseline_unit_cost`, `variance_pct`, `threshold_pct` | — |
| `outbound_order_rejected` | `location_id`, `country`, `currency`, `product_id`, `quantity`, `rejection_reason` | `product_category`, `unit`, `available_quantity` |
| `product_created` | `product_id`, `product_category`, `unit`, `country` | — |
| `inventory_form_validation_failed` | `form`, `field_name`, `error_code` | `location_id` |
| `supplier_rate_changed` | `supplier_id`, `country`, `currency`, `new_rate` | — |
| `incident_created` | `incident_id`, `category`, `status` | — |
| `login_succeeded` | `auth_method` | — |
| `login_failed` | `failure_reason`, `attempt_number_in_session` | — |
| `session_expired` | `expiry_cause`, `last_route` | — |
| `password_changed` | `method` | — |
| `api_latency_recorded` | `method`, `route_template`, `status_class`, `window_start`, `window_seconds`, `request_count`, `p50_ms`, `p95_ms`, `max_ms` | — |
| `page_load_measured` | `route_template`, `navigation_type`, `load_ms` | `lcp_ms` |
| `api_error_returned` | `method`, `route_template`, `status_code`, `error_category` | — |
| `frontend_error_captured` | `error_name`, `error_fingerprint`, `route_template`, `handled` | — |
| `page_viewed` | `route_template`, `section` | `referrer_route` |
| `flow_abandoned` | `flow`, `last_step_reached`, `elapsed_ms`, `fields_filled_count` | — |

### 7.3 Descripción de propiedades específicas

| Propiedad | Evento(s) | Tipo y significado |
|---|---|---|
| `inbound_order_id`, `outbound_order_id` | órdenes | Entero. Identificador de la orden; une el evento con la fila de base de datos |
| `unit_cost` | entrada, variación de precio | Número > 0, en la `currency` del local. **Opcional hasta que el modelo guarde el coste (B1)** |
| `baseline_unit_cost`, `variance_pct`, `threshold_pct` | variación de precio | Coste de referencia (media de las últimas 5 entradas del mismo producto y proveedor), variación en porcentaje y umbral aplicado (10) |
| `reason` | merma | `expired`, `kitchen_error` o `theft_suspected` (requiere B2) |
| `threshold_quantity` | umbral | Mínimo configurado para ese producto y local (requiere B4); `quantity` es el stock actual tras la orden |
| `triggering_outbound_order_id` | umbral | Orden de salida que provocó el cruce |
| `attempted_operation` | edición directa | `set_stock`, `adjust_stock` u `other`; `quantity` es la cantidad que se intentó fijar |
| `rejection_reason` | edición directa | `direct_edit_not_allowed` o `forbidden_role` |
| `rejection_reason` | salida rechazada | `insufficient_stock`, `ingredient_not_found`, `validation_error` o `database_error`; `available_quantity` es el stock disponible si se conoce |
| `form` | validación de formulario | `inbound_order`, `outbound_order` o `product_create` |
| `field_name`, `error_code` | validación de formulario | Nombre técnico del campo y código (`required`, `invalid_type`, `out_of_range`, `too_long`, `other`). Nunca el valor escrito |
| `supplier_id`, `new_rate`, `country`, `currency` | tarifa de proveedor | Identificador del proveedor, nueva tarifa y país/moneda del proveedor, con el mapa `Colombia`→`CO`, `USA`→`US` (B8) |
| `incident_id`, `category`, `status` | incidencia | Identificador, categoría y estado. **Nunca la descripción** |
| `auth_method` | inicio de sesión | `password` |
| `failure_reason`, `attempt_number_in_session` | login fallido | `invalid_credentials`, `validation_error` o `service_error`; contador de intentos en la sesión. **Nunca el usuario ni la contraseña** |
| `expiry_cause`, `last_route` | sesión caducada | `token_expired` o `token_invalid`; ruta (plantilla) donde ocurrió |
| `method` | cambio de contraseña | `change_password` o `reset_password` |
| `method`, `status_class`, `window_start`, `window_seconds`, `request_count`, `p50_ms`, `p95_ms`, `max_ms` | latencia | Verbo HTTP, clase de estado (`2xx`, `3xx`, `4xx`, `5xx`), inicio y duración de la ventana (60 s) y estadísticas de esa ventana |
| `navigation_type`, `load_ms`, `lcp_ms` | carga de página | `navigate`, `reload` o `back_forward`; milisegundos de carga y del elemento más grande visible |
| `status_code`, `error_category` | error de API | Código 500 a 599 y `database_unavailable` o `internal_error` |
| `error_name`, `error_fingerprint`, `handled` | error de frontend | Nombre del tipo de error, huella hash estable y si se capturó. **Sin mensaje ni traza** |
| `section`, `referrer_route` | página vista | `home`, `inventory`, `suppliers`, `incidents`, `account`, `auth` o `candidates`; ruta de origen |
| `flow`, `last_step_reached`, `elapsed_ms`, `fields_filled_count` | flujo abandonado | `inbound_order`, `outbound_order`, `incident_register` o `supplier_create`; último paso (`form_opened`, `field_edited`, `validation_failed`, `submit_started`), tiempo y **número** de campos rellenos (no su contenido) |

### 7.4 Datos sensibles y PII

| Dato | Tratamiento |
|---|---|
| `userId` | Identificador interno pseudónimo; **es dato personal indirecto**. Vive solo en el envelope, nunca en `properties`. Antes del login vale `anonymous` |
| Email, nombre, contraseña, token | **Nunca se capturan**, tampoco en `login_failed` ni en `password_changed` |
| Texto libre (descripción de incidencias, notas, mensajes de error) | Fuera de la allowlist; no se envía |
| URL completa y query string | Se sustituye por `route_template`. Una URL puede contener datos escritos por el usuario (por ejemplo, credenciales si un formulario se envía por GET) |
| Dirección IP y navegador | No se capturan |
| `supplier_name` | Nombre comercial de empresa; no personal. Si un proveedor es una persona física, se sustituiría por `supplier_id` |
| Importes y cantidades | Datos de negocio; se guardan en la moneda del local sin conversión |

La anonimización se hace **antes de emitir**: la allowlist se aplica en el origen del evento, no al leerlo después. Para análisis, `userId` se puede agregar por local o rol sin exponerlo en informes.


## 8. Estrategia de entrega

### 8.1 Stream o batch por evento

Criterio: la urgencia de la **decisión** que alimenta el evento, no la preferencia técnica. Si la decisión se toma en minutos mientras alguien trabaja, es **stream**. Si se toma en horas, días o semanas, es **batch** (lotes cada hora o cada día).

| `event_type` | Modo | Justificación |
|---|---|---|
| `stock_threshold_triggered` | **stream** | Un cocinero sin lomo de res en pleno servicio necesita que el local se reabastezca en minutos; un aviso al día llega tarde |
| `login_failed` | **stream** | Un ataque de fuerza bruta se corta en segundos; el contador de intentos por sesión solo sirve si es inmediato |
| `api_error_returned` | **stream** | Una caída de base de datos (503) afecta a todos los locales a la vez y operaciones debe enterarse mientras ocurre |
| `inbound_order_created` | batch (diario) | Consolidar compras se decide semanalmente; no cambia nada ver la entrada en segundos |
| `outbound_order_created` | batch (diario) | El pedido a proveedores se sugiere por ritmo de consumo del día anterior |
| `stock_waste_registered` | batch (diario) | La auditoría de merma se programa por locales y semanas, no por evento |
| `direct_stock_edit_rejected` | batch (diario) | La decisión es capacitar o ajustar permisos, que se toma por local y semana. Si la política cambia a "alertar por posible robo", se pasa a stream |
| `ingredient_price_variance_detected` | batch (cada hora) | Renegociar con un proveedor es un proceso de días; una hora de retraso es irrelevante. El lote horario permite agrupar alertas |
| `outbound_order_rejected` | batch (diario) | Decide conteos físicos programados, no acciones inmediatas |
| `product_created`, `supplier_rate_changed`, `incident_created` | batch (diario) | Decisiones de gestión semanales |
| `inventory_form_validation_failed`, `flow_abandoned`, `page_viewed`, `page_load_measured` | batch (diario) | Rediseño de pantallas y priorización de mejoras: se decide por tendencia |
| `login_succeeded`, `session_expired`, `password_changed` | batch (diario) | Dimensionar soporte y ajustar la duración del token son decisiones de tendencia |
| `api_latency_recorded` | batch (cada hora) | Priorizar optimizaciones es una decisión semanal; ya llega agregado por minuto |
| `frontend_error_captured` | batch (diario) | Se prioriza por frecuencia; un error aislado no exige reacción inmediata |

Resumen: **3 eventos en stream y 18 en batch**. Que el stream sea minoría es deliberado: cada pipeline en tiempo real cuesta más de mantener, y solo se justifica cuando alguien actúa en minutos.

### 8.2 Throttle y debounce para eventos de alta frecuencia

| Evento | Riesgo de volumen | Estrategia |
|---|---|---|
| `api_latency_recorded` | Una fila por petición sería el evento más voluminoso del sistema | **Agregación en origen**: un evento por ruta, método y clase de estado cada 60 s, con `request_count`, `p50_ms`, `p95_ms` y `max_ms`. No hay un evento por petición; el detalle por petición se queda en el log `api.timing` ya existente |
| `page_viewed` | Los re-renderizados repetirían la vista | Solo se emite en **cambio de ruta**; **debounce de 1 segundo** para ignorar redirecciones inmediatas y la misma ruta repetida |
| `page_load_measured` | Una medición por navegación | Una sola por navegación completa; sin muestreo mientras el volumen sea de 14 locales |
| `inventory_form_validation_failed` | Un usuario que teclea mal puede disparar decenas de errores | **Throttle**: como máximo 1 evento por formulario y campo cada 10 segundos y por sesión |
| `frontend_error_captured` | Un error en un bucle de render inundaría el canal | **Deduplicación por `error_fingerprint`**: máximo 5 eventos por huella, por sesión y por minuto |
| `login_failed` | Un ataque genera miles de intentos | Se emiten los primeros 20 por minuto y sesión; después se agrupan en un único evento con el contador `attempt_number_in_session` actualizado. Nunca se descarta sin contar |
| `stock_threshold_triggered` | Un producto bajo el mínimo repetiría la alerta con cada salida | **Disparo por cruce**: solo se emite al pasar de por encima a por debajo del mínimo; se vuelve a armar cuando el stock supera de nuevo el umbral |
| `flow_abandoned` | Varias salidas del mismo formulario | Se emite una sola vez por apertura del formulario, al salir de la ruta |

Reglas comunes: el reintento de envío conserva el mismo `eventId`; si el canal falla, el frontend guarda los eventos en memoria hasta un máximo de 100 y descarta los más antiguos, y la telemetría **nunca bloquea ni retrasa una acción del usuario**.

## 9. Riesgos y exclusiones

### 9.1 Eventos considerados y descartados

| Evento descartado | Motivo |
|---|---|
| `inventory_location_filter_changed` (cambio del filtro de local) | No habilita ninguna decisión distinta a la que ya da `page_viewed` |
| `product_row_expanded` (abrir "Ver stock por local") | Volumen alto y ninguna decisión de negocio concreta |
| Pulsaciones de teclado y movimientos de ratón | Alto coste, privacidad dudosa y sin decisión asociada |
| `password_reset_requested` (cada solicitud de "olvidé mi contraseña") | Registrarlo individualmente facilitaría enumerar cuentas existentes; el resultado final queda cubierto por `password_changed` |
| Cuerpo completo de peticiones y respuestas de la API | Contiene datos que no están en ninguna allowlist; el middleware actual ya registra solo método, ruta, estado y duración |
| Un evento por cada petición `GET` de listado | Cubierto por `api_latency_recorded` agregado; el coste por fila no compensa |
| `stock_level_viewed` | Es el mismo dato que ya refleja `stock_threshold_triggered` y la latencia de la consulta |

### 9.2 Datos que no se capturan por privacidad o coste

- **Nombres de empleados y datos de clientes**: nunca, tampoco en forma de texto libre.
- **Contenido de incidencias, notas y mensajes de error**: pueden incluir datos de clientes o información interna escrita por una persona.
- **URL completa, query string, dirección IP y navegador**: una URL puede arrastrar valores escritos por el usuario (incluso credenciales si un formulario se envía por GET).
- **Conversión de monedas**: queda fuera de la telemetría; la hace el reporte ejecutivo más adelante.
- **Datos por petición individual de latencia**: coste de almacenamiento sin decisión asociada; basta el agregado.

### 9.3 Riesgos del diseño

| Riesgo | Mitigación |
|---|---|
| Tres eventos obligatorios dependen de cambios de modelo que aún no existen (B1, B2, B4) y uno depende de una guarda nueva (B5) | El plan los define con campos opcionales o requisitos explícitos; deben implementarse en la fase de captura antes de emitir esos eventos |
| Sin `X-Request-Id` ni `X-Session-Id` (B6) no hay correlación entre frontend, backend y logs | Definirlos en el middleware y en la configuración CORS al empezar la instrumentación |
| Doble conteo de salidas si una merma emitiera a la vez `outbound_order_created` y `stock_waste_registered` | Son excluyentes por orden (ver sección 10) |
| Tamaño y retención de los datos | Propuesta: retener 13 meses los eventos de detalle y conservar agregados (por local, país y semana) más tiempo; se confirma con el pipeline de reporte |
| El `userId` es dato personal indirecto | Solo en el envelope, nunca en `properties`; informes agregados |
| Eventos de frontend manipulables por un usuario | Los eventos de negocio (órdenes, umbral, precio) nacen en el backend, no en el navegador; el frontend solo emite navegación, rendimiento y errores |
| La allowlist puede quedar obsoleta | Cada cambio sube `schemaVersion` y se revisa `event-schemas.json` |

## 10. Decisión de diseño más difícil

Decidir **cómo contar las salidas de merma sin duplicarlas**. El BRIEFING define `outbound_order_created` como consumo de ingredientes pero también dice que una orden de salida incluye la merma, y además exige `stock_waste_registered`. Si cada merma emitiera los dos eventos, cualquier suma de salidas por local contaría dos veces las pérdidas. Se decidió que **son excluyentes por orden**: una salida con `reason = consumption` emite solo `outbound_order_created`, y una con `reason = waste` emite solo `stock_waste_registered`, ambas con el mismo `outbound_order_id`. El total de salidas por local es la suma de ambos eventos y el reporte puede unir cada uno con su fila de base de datos.

### Resumen de cifras

| Concepto | Valor |
|---|---|
| Eventos diseñados | 21 |
| Obligatorios del BRIEFING | 6 |
| Identificados por nosotros | 15 |
| Categorías cubiertas | 5 (negocio, autenticación, rendimiento, errores, navegación) |
| Eventos en stream / batch | 3 / 18 |
| Eventos con allowlist de propiedades | 21 de 21 |

## 11. Almacenamiento: mapeo a la tabla `telemetry_events`

Cada evento aceptado se convierte en una fila de `telemetry_events` (Supabase). DDL en `services/api/sql/telemetry_events.sql`; explicación en `storage-notes.md`.

| Columna | Origen |
|---|---|
| `id` | `eventId` |
| `timestamp` | `timestamp` |
| `service` | constante `backoffice` |
| `event_type` | `event_type` |
| `level` | por tipo de evento (tabla de abajo) |
| `value` | número principal de `properties` (tabla de abajo) |
| `message` | resumen legible por tipo de evento; nunca incluye `userId` ni `sessionId` |
| `tags` | `properties` completas (solo claves del allowlist) + `session_id`, `user_id`, `request_id` y `schema_version` del envelope |

Los identificadores del envelope se guardan en `tags` porque el análisis posterior los necesita (sesiones, embudos por usuario, correlación con los logs). Ninguna propiedad de ningún allowlist usa esos cuatro nombres, así que no puede haber colisiones. `userId` es un identificador interno pseudónimo (sección 7.4): solo vive en `tags` y nunca en `properties`.

### Severidad (`level`)

| `level` | Eventos |
|---|---|
| `error` | `api_error_returned`; `frontend_error_captured` con `handled = false` |
| `warn` | `login_failed`, `session_expired`, `direct_stock_edit_rejected`, `outbound_order_rejected`, `stock_threshold_triggered`, `ingredient_price_variance_detected`; `frontend_error_captured` con `handled = true` |
| `info` | el resto de los eventos |

### Valor principal (`value`)

| Evento | Propiedad copiada a `value` |
|---|---|
| `inbound_order_created`, `outbound_order_created`, `stock_waste_registered`, `stock_threshold_triggered`, `direct_stock_edit_rejected`, `outbound_order_rejected` | `quantity` |
| `ingredient_price_variance_detected` | `variance_pct` |
| `supplier_rate_changed` | `new_rate` |
| `login_failed` | `attempt_number_in_session` |
| `api_latency_recorded` | `p95_ms` |
| `page_load_measured` | `load_ms` |
| `flow_abandoned` | `elapsed_ms` |
| resto | sin valor (`null`) |

La dimensión específica de Brasaland (local, país, producto, moneda) permanece en `tags` y se consulta con el índice GIN, por ejemplo `tags @> '{"country":"CO","location_id":1}'`. Las cantidades y costes se guardan en la moneda del local, sin conversión.