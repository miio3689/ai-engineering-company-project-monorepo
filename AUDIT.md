# Auditoría inicial de rendimiento frontend

## 1. Metodología y entorno

Las puntuaciones de la sección 2 se midieron con Lighthouse en el panel de DevTools de Chrome, sobre builds de producción (`npm run build` + `npm run start`) ejecutados en GitHub Codespaces, con las cuatro categorías activadas (Performance, Accessibility, Best Practices y SEO). Cada página y modo se midió **2 veces** y se conservó la segunda ejecución, porque la primera suele ser más lenta al no haber caché. Como el informe completo no cabía en una sola captura, cada medición está documentada con **3 capturas del mismo informe**, guardadas en `audit/before/`:

- `audit/before/backoffice/products/` y `audit/before/backoffice/incidents-list/`
- `audit/before/website/home/` y `audit/before/website/application/`

En cada carpeta, `01-` muestra las puntuaciones y las métricas (parte superior del informe), y `02-` y `03-` muestran el resto del informe desglosado (insights y diagnósticos). Existen versiones en escritorio y en móvil. En el backoffice se midió con la sesión iniciada y la opción «Clear storage» desmarcada. Al medir desde Codespaces, la latencia de red incluye el reenvío de puertos, por lo que los tiempos absolutos serán algo mayores que en local; las comparaciones antes/después usan el mismo método.

## 2. Tabla de puntuaciones iniciales

| Página | Dispositivo | Perf. | Acc. | BP | SEO | LCP | CLS | TBT | Captura |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Backoffice `/inventory/products` | Escritorio | 100 | 100 | 100 | 60 | 0,3 s | 0,009 | 0 ms | [01-products-desktop.png](audit/before/backoffice/products/01-products-desktop.png) |
| Backoffice `/inventory/products` | Móvil | 100 | 100 | 100 | 60 | 0,9 s | 0,035 | 20 ms | [01-products-mobile.png](audit/before/backoffice/products/01-products-mobile.png) |
| Backoffice `/incidents/list` | Móvil | 90 | 100 | 100 | 60 | 0,9 s | 0,21 | 10 ms | [01-incidents-list-mobile.png](audit/before/backoffice/incidents-list/01-incidents-list-mobile.png) |
| Backoffice `/incidents/list` | Escritorio | 77 | 100 | 100 | 60 | 0,3 s | 0,662 | 0 ms | [01-incidents-list-desktop.png](audit/before/backoffice/incidents-list/01-incidents-list-desktop.png) |
| Website `/` | Móvil | 95 | 96 | 100 | 58 | 2,9 s | 0,036 | 10 ms | [01-home-mobile.png](audit/before/website/home/01-home-mobile.png) |
| Website `/` | Escritorio | 100 | 96 | 100 | 58 | 0,7 s | 0,032 | 0 ms | [01-home-desktop.png](audit/before/website/home/01-home-desktop.png) |
| Website `/application.html` | Móvil | 100 | 100 | 100 | 54 | 1,1 s | 0,03 | 30 ms | [01-application-mobile.png](audit/before/website/application/01-application-mobile.png) |
| Website `/application.html` | Escritorio | 100 | 100 | 100 | 54 | 0,5 s | 0,015 | 0 ms | [01-application-desktop.png](audit/before/website/application/01-application-desktop.png) |

## 3. Problemas detectados

### P1. LCP móvil de la home y descubrimiento de la imagen

- **Síntoma:** LCP móvil de 2,9 s; los insights recibidos señalan mejora de entrega de imágenes por 185 KiB y recursos que bloquean renderizado. En escritorio se informan 164 KiB de mejora de imagen y «LCP request discovery».
- **Evidencia:** La imagen principal visible al inicio usa Unsplash, `photo-1544025162-d76694265947`, con `w=1200&q=80`; la segunda imagen también usa Unsplash. Los `<img>` tienen `alt`, pero no declaran `width`, `height`, `loading`, `fetchpriority` ni `srcset`: [index.html](uis/website/index.html#L163), [index.html](uis/website/index.html#L177). Antes del `<body>` hay un `<script src="https://cdn.tailwindcss.com"></script>` clásico, sin `defer`/`async`, que precede a la imagen y bloquea el análisis del HTML mientras descarga/ejecuta: [index.html](uis/website/index.html#L36).
- **Causa raíz:** Está demostrado que la imagen principal depende de un recurso remoto no servido responsivamente desde el sitio y que el script CDN síncrono precede su descubrimiento. El tamaño real transferido no se puede obtener del HTML; 185/164 KiB son ahorros estimados reportados, no el tamaño del archivo. **Hipótesis:** la imagen principal es el elemento LCP; para confirmarlo hace falta el detalle de elemento/recurso del informe Lighthouse.
- **Métrica afectada:** LCP y Performance móvil; descubrimiento de la solicitud LCP y oportunidades de imagen en escritorio.
- **Corrección propuesta:** convertir la imagen LCP en un recurso optimizado y responsivo, reservar su proporción con dimensiones y darle prioridad explícita; volver a medir antes de optimizar imágenes secundarias.

### P2. CLS elevado en `/incidents/list`

- **Síntoma:** CLS 0,662 en escritorio y 0,21 en móvil; el insight recibido es «Layout shift culprits».
- **Evidencia:** La ruta monta `IncidentSummary` y `IncidentList`: [page.tsx](uis/backoffice/app/incidents/list/page.tsx#L1), [page.tsx](uis/backoffice/app/incidents/list/page.tsx#L14). En `IncidentSummary`, el estado inicial es una sola línea «Cargando resumen…» y, al terminar la petición, se reemplaza por un total y cuatro desgloses (`Breakdown`), sin altura mínima ni skeleton equivalente: [incident-summary.tsx](uis/backoffice/components/incident-summary.tsx#L59), [incident-summary.tsx](uis/backoffice/components/incident-summary.tsx#L76), [incident-summary.tsx](uis/backoffice/components/incident-summary.tsx#L83). La lista también sustituye «Cargando listado…» por las tarjetas de todas las incidencias, sin espacio reservado: [incident-list.tsx](uis/backoffice/components/incident-list.tsx#L190), [incident-list.tsx](uis/backoffice/components/incident-list.tsx#L213). Los dos datos se solicitan asíncronamente: [use-incidents.ts](uis/backoffice/hooks/use-incidents.ts#L28), [use-incidents.ts](uis/backoffice/hooks/use-incidents.ts#L101).
- **Causa raíz:** La altura del contenido de resumen y lista no se reserva antes de recibir los datos; la inserción condicional de un bloque de cinco tarjetas y de un número variable de filas desplaza el contenido siguiente. La estructura de código demuestra este mecanismo. **Hipótesis:** el informe atribuye la mayor parte del 0,662 al resumen, por su gran diferencia de altura; sin el nodo/trace de Lighthouse no se puede asignar con certeza el porcentaje a resumen frente a lista.
- **Métrica afectada:** CLS y Performance, especialmente escritorio.
- **Corrección propuesta:** reservar una geometría estable con skeletons/espacios que se aproximen al contenido final, o mantener los bloques en el flujo con contenido de carga de altura equivalente; validar por separado resumen y lista.

### P3. Tailwind CDN síncrono y configuración duplicada

- **Síntoma:** La consola avisa que `cdn.tailwindcss.com` no debe usarse en producción; se reportan recursos de terceros y render-blocking en la home.
- **Evidencia:** Ambas páginas descargan Tailwind CDN síncronamente y definen una configuración inline extensa en el `<head>`: [index.html](uis/website/index.html#L36), [index.html](uis/website/index.html#L37), [application.html](uis/website/application.html#L18), [application.html](uis/website/application.html#L19). El CDN se ejecuta antes del contenido de la página y antes de descubrir la imagen LCP.
- **Causa raíz:** CSS se genera/entrega mediante JavaScript de terceros en tiempo de ejecución en vez de incluirse como CSS de producción local; el script clásico bloquea el parser. Las dos páginas mantienen copias de la misma configuración de tema.
- **Métrica afectada:** render-blocking, LCP/Performance y dependencia de terceros; el impacto exacto de cada recurso no está cuantificado por página.
- **Corrección propuesta:** compilar Tailwind en el build local y centralizar el tema en una sola configuración compartida, comprobando que se incluyan las clases dinámicas usadas por ambos HTML.

### P4. Contraste de texto en la home

- **Síntoma:** Accesibilidad 96 en ambas mediciones de la home.
- **Evidencia:** La paleta define `brasaPrimary: #C2410C` y `brasaCream: #FFF7ED`: [index.html](uis/website/index.html#L42). Sobre el bloque con fondo `brasaPrimary`, hay texto `brasaCream/75` de 14 px y `brasaCream/80`: [index.html](uis/website/index.html#L228), [index.html](uis/website/index.html#L229), [index.html](uis/website/index.html#L234). Calculando la composición de opacidad sobre ese fondo, el contraste aproximado es 3,41:1 para `/75` y 3,67:1 para `/80`, inferior al mínimo WCAG AA de 4,5:1 para texto normal. Las dos imágenes visibles de la home sí tienen `alt` descriptivo: [index.html](uis/website/index.html#L165), [index.html](uis/website/index.html#L179).
- **Causa raíz:** El color translúcido de texto reduce el contraste frente al fondo naranja. El defecto de contraste está demostrado por las clases y colores del HTML; sin el detalle de auditorías fallidas de Lighthouse no se puede asegurar que sea el único motivo del 96.
- **Métrica afectada:** Accesibilidad.
- **Corrección propuesta:** elegir combinaciones opacas que alcancen 4,5:1 para texto normal y volver a ejecutar la auditoría de contraste. No hay evidencia en el código revisado de que los `alt` de las imágenes de la home falten.

### P5. SEO de las rutas medidas

- **Website `/`:** tiene título, `lang="es"`, descripción, Open Graph y Schema.org. Tiene **dos** `meta name="description"`; `lang.js` actualiza solo el elemento con `id="meta-description"`, por lo que la primera descripción permanece en español al cambiar idioma: [index.html](uis/website/index.html#L6), [index.html](uis/website/index.html#L8), [index.html](uis/website/index.html#L16), [lang.js](uis/website/public/lang.js#L272). No declara canonical ni robots explícitos. Los dos `<img>` revisados tienen `alt`.
- **Website `/application.html`:** tiene título, descripción y `lang="es"`: [application.html](uis/website/application.html#L2), [application.html](uis/website/application.html#L6), [application.html](uis/website/application.html#L8). No declara canonical, robots, Open Graph ni datos estructurados; esos elementos sí aparecen en la home, pero no en esta página. El formulario asocia etiquetas a sus controles y la ruta no contiene imágenes que requieran `alt`.
- **Backoffice `/incidents/list` y `/inventory/products`:** los archivos de ruta no exportan metadatos propios: [page.tsx](uis/backoffice/app/incidents/list/page.tsx#L5), [page.tsx](uis/backoffice/app/inventory/products/page.tsx#L7). Heredan el título y descripción genéricos del layout (`Talent Pipeline Tracker` / gestión de candidaturas), aunque son incidencias e inventario: [layout.tsx](uis/backoffice/app/layout.tsx#L9), [layout.tsx](uis/backoffice/app/layout.tsx#L10), [layout.tsx](uis/backoffice/app/layout.tsx#L11). El layout sí declara `lang="es"`; no declara canonical ni robots explícitos. Las páginas usan encabezados y controles etiquetados; la tabla de inventario tiene caption y encabezados de columna. No se encontraron imágenes en esas rutas que carezcan de `alt`.
- **Causa raíz:** Descripción duplicada en home que impide una actualización consistente; ausencia de metadatos específicos en las páginas analizadas de backoffice; metadatos sociales/estructurados incompletos en la solicitud web.
- **Métrica afectada:** SEO (58 en home, 54 en formulario y 60 en ambas rutas del backoffice).
- **Corrección propuesta:** dejar una sola descripción actualizable por idioma; añadir canonical y metadatos sociales/estructurados pertinentes al formulario; definir título y descripción específicos en las rutas de inventario e incidencias. Añadir robots solo si existe una decisión deliberada de indexación; la ausencia de una etiqueta robots explícita no demuestra por sí sola un fallo.

### P6. Traducción cliente y geometría

- **Síntoma:** ambas páginas cargan `lang.js` con `defer`; el reporte no entrega una medición aislada atribuible a este script.
- **Evidencia:** El script actualiza texto, atributos, título y metadatos recorriendo el documento en `DOMContentLoaded`, lee/escribe `localStorage` y publica `window.BrasalandI18n`: [lang.js](uis/website/public/lang.js#L227), [lang.js](uis/website/public/lang.js#L255), [lang.js](uis/website/public/lang.js#L293), [lang.js](uis/website/public/lang.js#L301), [lang.js](uis/website/public/lang.js#L308). `alidation.js` depende de ese global: [alidation.js](uis/website/public/alidation.js#L126), [alidation.js](uis/website/public/alidation.js#L134). La etiqueta `defer` está en ambas páginas: [index.html](uis/website/index.html#L97), [application.html](uis/website/application.html#L40).
- **Causa raíz:** Traducción y manipulación del DOM ocurren en cliente y deben conservar orden/contrato global con el validador clásico. `defer` no equivale a un script parser-blocking. **Hipótesis:** cuando la preferencia guardada cambia textos a una variante de distinta longitud después del primer layout, puede contribuir a CLS; no hay evidencia de que explique el LCP de 2,9 s ni de su tamaño de impacto.
- **Métrica afectada:** potencial CLS; JavaScript/CPU y consistencia de metadatos, sin impacto aislado cuantificado.
- **Corrección propuesta:** medir el CLS por separado en ambos idiomas y con/sin preferencia guardada antes de cambiar este flujo; si se confirma, evitar el cambio de geometría tras el primer render sin romper el global consumido por el formulario.

## 4. Análisis de duplicaciones

1. **`fieldClass` en nueve formularios/componentes.** Está en [account-profile.tsx](uis/backoffice/components/account-profile.tsx#L5), [auth-form.tsx](uis/backoffice/components/auth-form.tsx#L8), [change-password-form.tsx](uis/backoffice/components/change-password-form.tsx#L5), [create-supplier-form.tsx](uis/backoffice/components/create-supplier-form.tsx#L11), [forgot-password-form.tsx](uis/backoffice/components/forgot-password-form.tsx#L7), [incident-register-form.tsx](uis/backoffice/components/incident-register-form.tsx#L37), [inventory-inbound-form.tsx](uis/backoffice/components/inventory-inbound-form.tsx#L34), [inventory-outbound-form.tsx](uis/backoffice/components/inventory-outbound-form.tsx#L53) y [reset-password-form.tsx](uis/backoffice/components/reset-password-form.tsx#L8). Es candidata para normalizar foco, altura y bordes, pero hay variantes de `border` y `text-base`; una abstracción debe permitir clases adicionales, no borrar esas diferencias. Firma posible: `getFormFieldClass(variant?: "default" | "error", className?: string): string`.
2. **Formato numérico de inventario.** `Intl.NumberFormat("es-ES", { maximumFractionDigits: 3 })` aparece en entrada, salida y tabla: [inventory-inbound-form.tsx](uis/backoffice/components/inventory-inbound-form.tsx#L36), [inventory-outbound-form.tsx](uis/backoffice/components/inventory-outbound-form.tsx#L55), [inventory-products-table.tsx](uis/backoffice/components/inventory-products-table.tsx#L26). Ya existe `formatQuantity` en [inventory-format.ts](uis/backoffice/lib/inventory-format.ts#L1) y se usa en la lista de órdenes, pero no en esos tres sitios: [inventory-orders-list.tsx](uis/backoffice/components/inventory-orders-list.tsx#L6). En cambio, `formatQuantityUnit` **no está repetido con ese nombre**: solo aparece en salida; entrada implementa condicionalmente la pluralización en línea ([inventory-outbound-form.tsx](uis/backoffice/components/inventory-outbound-form.tsx#L59), [inventory-inbound-form.tsx](uis/backoffice/components/inventory-inbound-form.tsx#L127)). Candidata: reutilizar `formatQuantity` y añadir `formatQuantityWithUnit(quantity: number, unit: IngredientUnit): string` para compartir también la regla de unidad.
3. **Bloqueo de doble envío.** Entrada y salida repiten `submittingRef`, `isSubmitting`, bloqueo al entrar y liberación en `finally`: [inventory-inbound-form.tsx](uis/backoffice/components/inventory-inbound-form.tsx#L52), [inventory-inbound-form.tsx](uis/backoffice/components/inventory-inbound-form.tsx#L100), [inventory-inbound-form.tsx](uis/backoffice/components/inventory-inbound-form.tsx#L117), [inventory-outbound-form.tsx](uis/backoffice/components/inventory-outbound-form.tsx#L78), [inventory-outbound-form.tsx](uis/backoffice/components/inventory-outbound-form.tsx#L133), [inventory-outbound-form.tsx](uis/backoffice/components/inventory-outbound-form.tsx#L151). Las operaciones de negocio y manejo de errores sí difieren. Firma posible: `useSubmissionLock(): { isSubmitting: boolean; run<T>(operation: () => Promise<T>): Promise<T | undefined> }`.
4. **Error recuperable con «Reintentar».** Estructuras equivalentes aparecen en [incident-list.tsx](uis/backoffice/components/incident-list.tsx#L194), [incident-summary.tsx](uis/backoffice/components/incident-summary.tsx#L64), [inventory-products-table.tsx](uis/backoffice/components/inventory-products-table.tsx#L48), [inventory-inbound-form.tsx](uis/backoffice/components/inventory-inbound-form.tsx#L204) y [inventory-outbound-form.tsx](uis/backoffice/components/inventory-outbound-form.tsx#L268). Candidata de UI: `RetryableError({ message, onRetry, className? })`; conservar `role="alert"` y los estilos particulares requeridos por cada contexto.
5. **Tema Tailwind repetido en las páginas web.** Los bloques de configuración inline en [index.html](uis/website/index.html#L37) y [application.html](uis/website/application.html#L19) repiten colores, fuentes e imagen de fondo. Candidata: una única configuración de build compartida; también eliminaría la deriva entre páginas, aunque el cambio forma parte de la migración del CDN, no de una extracción aislada.

**Mejor candidata a custom hook:** el bloqueo de envío de entrada/salida. Es lógica de comportamiento idéntica (no solo una cadena CSS) que evita dobles solicitudes y garantiza liberar el estado incluso al fallar, mientras deja intacta la validación y la respuesta específica de cada operación. La segunda candidata más directa es `RetryableError`, que centraliza semántica y accesibilidad del patrón visual repetido. Ninguna extracción se implementa en esta fase.

## 5. Orden de corrección propuesto

Cada punto se debe validar y entregar como un cambio independiente (un problema por commit; no se realizó ningún commit en esta auditoría):

1. **LCP móvil:** optimizar y hacer responsiva la imagen hero y priorizar su descarga; comprobar el nodo LCP real en el informe y medir de nuevo móvil/escritorio.
2. **Render-blocking/terceros:** reemplazar Tailwind CDN por CSS generado en build y centralizar su configuración; medir LCP y Performance tras separar este cambio del de imagen.
3. **CLS de incidencias:** reservar espacio o usar placeholders de geometría estable en resumen y lista; volver a medir escritorio y móvil, verificando los elementos culpables.
4. **Accesibilidad de home:** corregir primero las combinaciones con contraste insuficiente y repetir la auditoría completa de accesibilidad.
5. **SEO:** corregir la descripción duplicada y añadir metadatos específicos por ruta; validar el HTML final de cada página.
6. **Traducción cliente:** solo si pruebas por idioma confirman CLS/CPU atribuible, modificar el flujo de traducción y volver a medir.
7. **Duplicaciones internas:** extraer `useSubmissionLock`, reutilizar `formatQuantity` y valorar `RetryableError`/clases de campo en cambios separados; no se espera una mejora de Lighthouse por sí sola, así que van después de los problemas métricos demostrados.

TTFB e INP quedan fuera de la priorización cuantitativa hasta obtener mediciones. Los TBT facilitados son bajos (0–30 ms); no justifican atribuir el problema principal a ejecución larga de JavaScript sin trazas adicionales.

## Resultados tras las correcciones

| Página | Modo | Perf. inicial → final | Acc./BP/SEO | LCP inicial → final | CLS inicial → final | TBT inicial → final | Capturas / nota |
|---|---|---:|---|---|---|---|---|
| Backoffice `/inventory/products` | Escritorio | 100 → 100 | 100/100/60 | 0,3 → 0,3 s | 0,009 → 0,009 | 0 → 0 ms | [Antes](audit/before/backoffice/products/01-products-desktop.png); sin cambios, no se volvió a medir |
| Backoffice `/inventory/products` | Móvil | 100 → 100 | 100/100/60 | 0,9 → 0,9 s | 0,035 → 0,035 | 20 → 20 ms | [Antes](audit/before/backoffice/products/01-products-mobile.png); sin cambios, no se volvió a medir |
| Backoffice `/incidents/list` | Escritorio | 77 → 100 | 100/100/60 | 0,3 → 0,3 s | 0,662 → 0,026 | 0 → 0 ms | [Después Fix 1](audit/after/backoffice/incidents-list/01-incidents-list-desktop-fix1.png) |
| Backoffice `/incidents/list` | Móvil | 90 → 100 | 100/100/60 | 0,9 → 0,9 s | 0,21 → 0,049 | 10 → 10 ms | [Después Fix 1](audit/after/backoffice/incidents-list/01-incidents-list-mobile-fix1.png) |
| Website `/` | Escritorio | 100 → 100 | 96/100/58 | 0,7 → 0,6 s | 0,032 → 0,045 | 0 → 0 ms | [Después Fix 3](audit/after/website/home/01-home-desktop-fix3.png); CLS varió ligeramente, sigue en verde |
| Website `/` | Móvil | 95 → 100 | 96/100/58 | 2,9 → 1,0 s | 0,036 → 0,036 | 10 → 0 ms | [Después Fix 3](audit/after/website/home/01-home-mobile-fix3.png) |
| Website `/application.html` | Escritorio | 100 → 100 | 100/100/54 | 0,5 → 0,3 s | 0,015 → 0,015 | 0 → 0 ms | [Después Fix 3](audit/after/website/application/01-application-desktop-fix3.png) |
| Website `/application.html` | Móvil | 100 → 100 | 100/100/54 | 1,1 → 0,9 s | 0,03 → 0,029 | 30 → 20 ms | [Después Fix 3](audit/after/website/application/01-application-mobile-fix3.png) |

Los valores de productos son los de la medición inicial: no se volvieron a medir porque esa página no cambió. Las capturas `-fixN` corresponden a la medición posterior al fix indicado; cuando no hubo cambios posteriores en esa página, representan también el estado final. El detalle de las mediciones intermedias, commits, fixes no aplicados y limitaciones está en [REPORT.md](REPORT.md).


