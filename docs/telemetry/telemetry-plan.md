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