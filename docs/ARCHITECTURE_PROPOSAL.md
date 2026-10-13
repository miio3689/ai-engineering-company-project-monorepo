# Propuesta de arquitectura del backend de Brasaland

> Documento de razonamiento técnico. No contiene código ni crea estructura real en `services/`.
> Es independiente de [`.github/architecture.md`](../.github/architecture.md), que describe el frontend Next.js del Talent Pipeline Tracker y no se modifica.

## Fuentes de contexto utilizadas

- [`CONTEXT.md`](../CONTEXT.md): Brasaland centra su valor en el **servicio** y en ofrecer **pedidos online** a los clientes, con empleados bien formados. Define dos departamentos prioritarios (Marketing y experiencia digital; Formación y estándares de calidad) y dos agentes de IA:
  - Recomendaciones de producto a partir del historial de compras, productos más repetidos y frecuencia de compra.
  - Distribución automática de recetas: crear/actualizar receta, notificar a los locales, registrar quién ha leído el contenido y actualizar el material de formación.
- [`memory-bank/projectbrief.md`](../memory-bank/projectbrief.md): cadena fundada en Medellín en 2008, **14 restaurantes en Colombia y Florida**, unos 115 empleados y ~6 M USD de facturación anual.
- [`memory-bank/techContext.md`](../memory-bank/techContext.md): monorepo con `uis/` (frontends) y `services/` (backend de Hito 4).

Nota: `CONTEXT.md` no detalla por sí mismo los dominios de compras, operaciones o RR. HH.; esos dominios se derivan de la descripción de la cadena (restaurantes, empleados, pedidos) y de los dos agentes de IA, y deberán validarse con negocio.

---

## 1. Patrón arquitectónico

**Propuesta: monolito modular con arquitectura en capas dentro de cada módulo de dominio** (router → servicio → repositorio), desplegado como una única aplicación FastAPI.

### Por qué encaja con Brasaland

| Característica real | Consecuencia arquitectónica |
|---|---|
| 14 locales y ~115 empleados, ~6 M USD/año: escala media, equipo técnico pequeño | Un solo despliegue es suficiente. Los microservicios o el serverless por función añadirían coste operativo (orquestación, observabilidad distribuida) que la empresa no necesita. |
| Dos países (Colombia y Florida) | La variación (moneda, impuestos, idioma, zona horaria, normativa laboral) se concentra en la capa de servicios de cada dominio y en `core/`, sin duplicar el sistema por país. Cada local lleva su país/región como dato. |
| Varios dominios con reglas distintas: operaciones/ventas, compras/proveedores, marketing/fidelización, personas/cultura, formación, tecnología/API central | Un módulo por dominio con fronteras claras. Cada departamento puede evolucionar sus reglas sin tocar las de los demás. |
| Agentes de IA planificados (recomendaciones, distribución de recetas) | Los agentes necesitan consumir datos de varios dominios (pedidos + clientes + menú; recetas + locales + formación). Es más sencillo exponer esos datos mediante servicios internos de un monolito que mediante llamadas de red entre microservicios. |
| Pedidos online como núcleo del servicio | El flujo de pedidos requiere consistencia transaccional (pedido, pago, fidelización). Una base de datos única con transacciones es más segura que consistencia eventual entre servicios. |
| Cargas de trabajo asíncronas puntuales (notificaciones a locales, push de recomendaciones) | Se resuelven con tareas en segundo plano (`BackgroundTasks` o una cola) dentro del mismo monolito; solo se plantearía serverless para picos concretos más adelante. |

### Alternativas descartadas

- **MVC clásico**: está pensado para renderizar vistas en servidor. Aquí los frontends son aplicaciones independientes (`uis/`) y el backend solo expone una API JSON; la "V" no existe.
- **Microservicios**: justificados con muchos equipos o necesidades de escalado dispares. No es el caso con ~115 empleados y un equipo de ingeniería reducido.
- **Serverless puro**: el acoplamiento de los dominios con una BD relacional y el despliegue de muchas funciones pequeñas dificultan las transacciones de pedido y encarecen el desarrollo local. Se deja como opción para tareas puntuales.

### Capas dentro de cada módulo

1. **Router (capa de API)**: HTTP, validación de entrada/salida, códigos de estado. Sin reglas de negocio.
2. **Servicio (capa de negocio)**: reglas del dominio (por ejemplo, qué cuenta como "producto favorito").
3. **Repositorio (capa de datos)**: acceso a la base de datos.

Regla de dependencia: un módulo solo se comunica con otro a través de la interfaz pública de su servicio, nunca accediendo a sus modelos o repositorios.

---

## 2. Estructura de carpetas y módulos propuesta

Estructura a ubicar en `services/` (solo descriptiva, sin crearse):

```text
services/
└── api/
    ├── app/
    │   ├── main.py                  # creación de la app, registro de routers, middleware (CORS)
    │   ├── core/
    │   │   ├── config.py            # settings desde variables de entorno
    │   │   ├── database.py          # sesión/engine
    │   │   ├── security.py          # autenticación y autorización
    │   │   ├── errors.py            # excepciones y manejadores comunes
    │   │   └── dependencies.py      # dependencias compartidas
    │   ├── modules/
    │   │   ├── locations/           # 14 locales, país, horarios
    │   │   ├── sales/               # pedidos (online y en local), pagos
    │   │   ├── menu/                # productos, categorías, recetas
    │   │   ├── suppliers/           # proveedores y compras
    │   │   ├── customers/           # clientes, fidelización, recomendaciones
    │   │   ├── hr/                  # personas y cultura (empleados, selección)
    │   │   ├── training/            # formación, lectura de recetas, estándares
    │   │   └── notifications/       # envío a locales y a clientes (app/push)
    │   │       # cada módulo contiene:
    │   │       #   router.py, schemas.py, models.py, service.py, repository.py, dependencies.py
    │   └── agents_api/              # puntos de entrada para los agentes de IA (usan servicios, no BD)
    ├── tests/
    │   └── modules/<dominio>/
    ├── migrations/
    ├── pyproject.toml
    └── .env.example
```

### Criterio de separación

1. **Un módulo por dominio de negocio**, alineado con los departamentos de Brasaland. Cada módulo tiene un responsable de negocio claro.
2. **Cohesión interna por dominio, no por tipo técnico**: dentro de un módulo viven juntos router, esquemas, modelos y servicio, para que un cambio en "formación" afecte solo a `training/`.
3. **`core/` solo contiene lo transversal** (configuración, BD, seguridad, errores). Si algo es de un dominio concreto, no va a `core/`.
4. **`training` y `menu` separados**: la receta pertenece a `menu` (fuente de verdad), y `training` guarda el material derivado y el registro de lectura. Esto refleja el agente de distribución de recetas: al cambiar una receta, `menu` emite el cambio y `training` actualiza contenido y `notifications` avisa a los locales.
5. **`customers` agrupa fidelización y recomendaciones**: el agente de recomendaciones necesita historial, favoritos y frecuencia; los datos de compra los entrega `sales` mediante su servicio.
6. **`notifications` es transversal pero con entidad propia**, porque lo usan tanto Marketing (notificaciones a clientes) como Formación (notificaciones a locales).
7. **`hr` es independiente**: separa datos sensibles de personas. Podría absorber el flujo de candidaturas del Talent Pipeline Tracker (Hito 3), hoy resuelto en el frontend.

---

## 3. Organización de endpoints y routers

Todas las rutas bajo un prefijo de versión (`/api/v1`). Cada dominio expone un único router; la agrupación sigue el recurso principal.

| Router / dominio | Rutas (descripción) | Criterio de agrupación |
|---|---|---|
| `/locations/*` | Listado y detalle de locales; filtro por país (Colombia / Florida); horarios; estado operativo. | Todo lo que identifica un restaurante físico. Los demás dominios referencian el local por su identificador. |
| `/sales/*` | Pedidos (crear, consultar, cambiar estado), pagos, resúmenes de ventas por local y periodo. | Flujo transaccional del servicio y pedidos online. |
| `/menu/*` | Productos, categorías, precios por país, recetas y sus versiones. | Catálogo y recetas: fuente de verdad de lo que se vende y se prepara. |
| `/suppliers/*` | Proveedores, órdenes de compra, recepción de mercancía. | Compras y abastecimiento, separado de ventas. |
| `/customers/*` | Clientes, historial de compras, favoritos, puntos de fidelización, preferencias de notificación, recomendaciones personalizadas (`/customers/{id}/recommendations`). | Marketing y experiencia digital centrados en el cliente. |
| `/hr/*` | Empleados, candidaturas y etapas de selección, notas de candidatos. | Personas y cultura; datos sensibles con permisos propios. |
| `/training/*` | Contenidos de formación, asignación de contenido por local, registro de lectura (quién lo leyó y cuándo), estado de actualización tras una nueva receta. | Estándares de calidad y formación. |
| `/notifications/*` | Notificaciones a locales y a clientes, estado de entrega. | Canal de comunicación transversal. |
| `/health` y `/meta/*` | Salud del servicio y versión. | Tecnología/API central; sin lógica de negocio. |

Criterios generales:

- Rutas en plural y orientadas a recursos; las acciones que no son CRUD se modelan como subrecursos (`/training/contents/{id}/reads`).
- Las relaciones entre dominios se expresan con identificadores, no con rutas anidadas de otro dominio (por ejemplo, ventas de un local: `/sales/orders?location_id=...`, no `/locations/{id}/sales`), para evitar que `locations` dependa de `sales`.
- La autenticación y los permisos se aplican por router: `hr` y `suppliers` requieren roles internos; `customers` y `sales` combinan acceso de cliente y de personal.

---

## 4. Investigación: convenciones estándar de FastAPI

### Fuentes consultadas

Nota de transparencia: en esta sesión no se dispone de navegación web en vivo, por lo que lo siguiente se basa en documentación y repositorios de referencia ampliamente conocidos. Las URLs deben verificarse al revisar el documento y confirmar que siguen vigentes.

1. Documentación oficial de FastAPI, "Bigger Applications - Multiple Files" (`APIRouter`, `include_router`, estructura con `routers/`, `dependencies.py`, `internal/`): <https://fastapi.tiangolo.com/tutorial/bigger-applications/>
2. Documentación oficial de FastAPI, "Dependencies" (inyección de dependencias con `Depends`): <https://fastapi.tiangolo.com/tutorial/dependencies/>
3. Documentación oficial de FastAPI, "Settings and Environment Variables" (`pydantic-settings`): <https://fastapi.tiangolo.com/advanced/settings/>
4. Documentación oficial de FastAPI, "Handling Errors" y "CORS": <https://fastapi.tiangolo.com/tutorial/handling-errors/> y <https://fastapi.tiangolo.com/tutorial/cors/>
5. Plantilla oficial "Full Stack FastAPI Template" (carpeta `backend/app` con `api/`, `core/`, `models`, `crud`): <https://github.com/fastapi/full-stack-fastapi-template>
6. Repositorio comunitario "FastAPI Best Practices" de zhanymkanov, que defiende la estructura **por dominio** (`src/<dominio>/router.py, schemas.py, models.py, service.py, dependencies.py, exceptions.py`) frente a la estructura por tipo de fichero: <https://github.com/zhanymkanov/fastapi-best-practices>

### Convenciones identificadas

| Convención | Fuente | Cómo se refleja en la propuesta |
|---|---|---|
| Dividir la app en `APIRouter` registrados con `include_router` en `main.py` | 1 | Un `router.py` por módulo; `main.py` solo los registra (sección 3). |
| Separar esquemas Pydantic (entrada/salida) de modelos de BD | 5, 6 | `schemas.py` y `models.py` separados en cada módulo. |
| Configuración centralizada con `core/config.py` y variables de entorno | 3, 5 | `core/config.py` y `.env.example`; ningún secreto en el código. |
| Inyección de dependencias con `Depends` (sesión de BD, usuario actual, permisos) | 2 | `core/dependencies.py` para lo común y `dependencies.py` por módulo para lo específico. |
| Estructura por dominio en proyectos grandes frente a estructura por tipo | 6 (y 1, que ya agrupa por router) | Se adopta `modules/<dominio>/` en lugar de carpetas globales `routers/`, `models/`, `schemas/`. |
| Capa de servicio/CRUD separada del router | 5, 6 | `service.py` (reglas) y `repository.py` (acceso a datos), con routers delgados. |
| Manejo de errores con excepciones propias y manejadores globales | 4, 6 | `core/errors.py` define el formato único de error; cada módulo lanza excepciones propias. |
| CORS configurado en `main.py` con orígenes permitidos explícitos | 4 | Ver sección 5. |

### Cómo influyeron en la estructura (sección 2)

- La plantilla oficial usa carpetas por tipo (`models`, `crud`, `api/routes`). Para un proyecto pequeño es válido, pero con ocho dominios de negocio los ficheros globales crecerían sin control y cada cambio tocaría varias carpetas. Se adoptó entonces la estructura **por dominio** de la fuente 6, que además coincide con los departamentos de Brasaland.
- Se mantuvo de la plantilla oficial la separación `core/` (transversal) frente a lo específico, y la configuración mediante variables de entorno.
- La inyección de dependencias de FastAPI se usa para permisos por router (RR. HH. y compras restringidos) y para la sesión de BD, lo que facilita sustituir dependencias en las pruebas.
- Se añadió `agents_api/`, que no es una convención FastAPI: es una decisión propia derivada de `CONTEXT.md` para que los agentes de IA consuman servicios con contratos estables.

---

## 5. Separación frontend / backend como sistemas independientes

### Monorepo o repositorios separados

| Criterio | Monorepo (elegido) | Repos separados |
|---|---|---|
| Equipo pequeño, cambios que cruzan frontend y backend (p. ej. nuevo campo en candidato) | Un único PR y revisión | Coordinar varios PR y versiones |
| Contratos de API y tipos compartidos | Posibles en `packages/shared` | Requieren publicar paquetes |
| Despliegue independiente | Posible: cada carpeta con su propio `package.json`/`pyproject.toml` y su pipeline | Natural |
| Riesgo | Acoplamiento accidental si no hay normas | Divergencia de contratos |

Brasaland ya es un monorepo y [`AGENTS.md`](../AGENTS.md) lo exige, por lo que se mantiene. La independencia se consigue por **fronteras de carpeta y de despliegue**, no por repositorios.

### Organización real del monorepo

```text
uis/website/      # web pública
uis/backoffice/   # aplicación interna (Next.js, Talent Pipeline Tracker)
services/         # backend FastAPI propuesto
packages/shared/  # tipos compartidos
```

El frontend de `uis/backoffice` ya muestra el patrón: según [`.github/architecture.md`](../.github/architecture.md), toda la comunicación con la API se centraliza en `services/` (`services/api.ts`), los tipos viven en `types/models.ts` y las páginas de `app/` no acceden directamente a la API. Por ello, cuando exista el backend FastAPI, solo habrá que cambiar el destino de las llamadas en ese fichero, sin tocar componentes ni páginas.

### Comunicación

- **API REST con JSON** bajo `/api/v1`. FastAPI genera OpenAPI automáticamente, que sirve como contrato entre equipos y como base para generar tipos TypeScript.
- Los frontends nunca acceden a la BD ni a módulos del backend; solo consumen HTTP.
- Los agentes de IA usan `agents_api/` y no un acceso directo a la BD.

### Variables de entorno

- Cada sistema tiene su configuración aislada (coherente con `techContext.md`: "configuración aislada por aplicación o servicio").
- Frontends: una URL base de la API (por ejemplo `NEXT_PUBLIC_API_BASE_URL` en Next.js); solo valores no secretos en variables públicas.
- Backend: `.env` leído por `core/config.py` (cadena de BD, claves, orígenes CORS permitidos). Se versiona únicamente `.env.example`; nunca los `.env` reales.
- Valores distintos por entorno (local/Codespaces, staging, producción).

### CORS

- Necesario porque el navegador considera orígenes distintos al sitio público, al backoffice y a la API (distintos dominios o puertos).
- Se configura en `main.py` con una **lista explícita** de orígenes tomada de `core/config.py` (website y backoffice de cada entorno), sin `*` si se usan credenciales.
- Limitar métodos y cabeceras a los necesarios.
- En desarrollo (Codespaces) los orígenes cambian por puerto reenviado; se resuelve con la variable de entorno, no editando código.
- Alternativa: un proxy o *rewrite* en Next.js hacia la API para evitar CORS en el backoffice; es opcional y se puede decidir después.

---

## 6. Riesgos y puntos de atención

| # | Riesgo | Cómo se manifestaría en Brasaland | Mitigación |
|---|---|---|---|
| 1 | **Acoplamiento entre dominios** | `customers` importando directamente los modelos de `sales` para calcular favoritos, o `training` consultando tablas de `menu`. Un cambio en pedidos rompería recomendaciones y formación. | Comunicación solo por servicios públicos de cada módulo; revisión de imports en PR; reglas de lint de dependencias entre módulos. |
| 2 | **Lógica de negocio en los routers** | Cálculo de puntos de fidelización o decisión de "receta nueva vs. actualización" dentro del endpoint; los agentes de IA no podrían reutilizarla sin llamar por HTTP. | Routers delgados; reglas únicamente en `service.py`; pruebas unitarias sobre servicios. |
| 3 | **Manejo de errores inconsistente** | `sales` devuelve `404` con un formato, `hr` otro, y los frontends (`services/api.ts`) tienen que manejar cada caso. | Formato de error único en `core/errors.py` y excepciones base compartidas. |
| 4 | **Diferencias entre Colombia y Florida resueltas con condicionales dispersos** | `if country == "US"` repetido en ventas, menú y RR. HH. | Centralizar monedas, impuestos y zonas horarias en `core/` y en políticas por país dentro de cada servicio. |
| 5 | **Datos sensibles de RR. HH. y clientes expuestos** | Candidaturas y datos de clientes accesibles sin permisos suficientes, o enviados a los agentes de IA sin necesidad. | Permisos por router con dependencias; esquemas de salida mínimos; `agents_api/` solo con campos necesarios. |
| 6 | **Divergencia entre contrato de API y frontends** | El backoffice (Hito 3) usa tipos definidos a mano que se desalinean con FastAPI. | Usar OpenAPI como fuente del contrato; pruebas de contrato; tipos compartidos o generados. |
| 7 | **Convertir `core/` en cajón de sastre** | Reglas de dominio acaban en `core/` por comodidad. | Solo infraestructura transversal en `core/`; todo lo demás, en su módulo. |

---

## Decisiones pendientes de validar

- Elección de base de datos y ORM.
- Estrategia de autenticación (clientes frente a personal interno).
- Cuándo extraer `notifications` a una cola o proceso separado.
- Si el flujo de candidaturas del Hito 3 migrará a `hr/` (requiere confirmación, ya que Hito 3 es zona protegida).
