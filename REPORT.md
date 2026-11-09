# Informe de auditoría de rendimiento frontend

## 1. Resumen ejecutivo

El **Fix 1** fue el que más elevó una puntuación: en `/incidents/list` escritorio Performance pasó de 77 a 100 y CLS de 0,662 a 0,026. El **Fix 2** redujo el LCP móvil de la home de 2,9 s a 1,1 s; el **Fix 3** lo llevó a 1,0 s y sustituyó Tailwind CDN por CSS local compilado. El **Fix 4** extrajo un hook de doble envío para dos formularios de inventario y no afecta las páginas medidas por Lighthouse. El contraste de la home y su meta description duplicada siguen pendientes.

## 2. Entorno y método

Lighthouse se ejecutó en Chrome sobre builds de producción en GitHub Codespaces. Se hicieron dos ejecuciones por página y modo, conservando la segunda, con el mismo método de medición. Las capturas `-fixN` corresponden a la medición después de ese fix; al no haber cambios posteriores en esa página, también representan el estado final. `audit/after/backoffice/incidents-list/` corresponde al Fix 1, las capturas `home/*-fix2` al Fix 2 y `home/*-fix3` / `application/*-fix3` al Fix 3.

Codespaces añade latencia del reenvío de puertos: las comparaciones antes/después son consistentes entre sí, pero no equivalen a una medición local. No se midieron TTFB ni INP.

Commits de preparación y línea base: [Scripts de producción](https://github.com/miio3689/ai-engineering-company-project-monorepo/commit/dbc2ae768e1ae8c2cea7e4412602ac69ffefaec1) y [Medición inicial y AUDIT.md](https://github.com/miio3689/ai-engineering-company-project-monorepo/commit/be982d08c7086d6d643476f28c2f2b2860844a5d).

## 3. Resumen antes y después

Los valores de puntuación se muestran como `Performance/Accesibilidad/Best Practices/SEO`. En productos se conserva la línea base porque no se volvió a medir.

| Página | Modo | Puntuaciones antes → después | LCP antes → después | CLS antes → después | TBT antes → después | Evidencia final |
|---|---|---|---|---|---|---|
| Backoffice `/inventory/products` | Escritorio | 100/100/100/60 → 100/100/100/60 | 0,3 → 0,3 s | 0,009 → 0,009 | 0 → 0 ms | Sin cambios, no se volvió a medir: [antes](audit/before/backoffice/products/01-products-desktop.png) |
| Backoffice `/inventory/products` | Móvil | 100/100/100/60 → 100/100/100/60 | 0,9 → 0,9 s | 0,035 → 0,035 | 20 → 20 ms | Sin cambios, no se volvió a medir: [antes](audit/before/backoffice/products/01-products-mobile.png) |
| Backoffice `/incidents/list` | Escritorio | 77/100/100/60 → 100/100/100/60 | 0,3 → 0,3 s | 0,662 → 0,026 | 0 → 0 ms | [antes](audit/before/backoffice/incidents-list/01-incidents-list-desktop.png), [después Fix 1](audit/after/backoffice/incidents-list/01-incidents-list-desktop-fix1.png) |
| Backoffice `/incidents/list` | Móvil | 90/100/100/60 → 100/100/100/60 | 0,9 → 0,9 s | 0,21 → 0,049 | 10 → 10 ms | [antes](audit/before/backoffice/incidents-list/01-incidents-list-mobile.png), [después Fix 1](audit/after/backoffice/incidents-list/01-incidents-list-mobile-fix1.png) |
| Website `/` | Escritorio | 100/96/100/58 → 100/96/100/58 | 0,7 → 0,6 s | 0,032 → 0,045 | 0 → 0 ms | [antes](audit/before/website/home/01-home-desktop.png), [final Fix 3](audit/after/website/home/01-home-desktop-fix3.png) |
| Website `/` | Móvil | 95/96/100/58 → 100/96/100/58 | 2,9 → 1,0 s | 0,036 → 0,036 | 10 → 0 ms | [antes](audit/before/website/home/01-home-mobile.png), [final Fix 3](audit/after/website/home/01-home-mobile-fix3.png) |
| Website `/application.html` | Escritorio | 100/100/100/54 → 100/100/100/54 | 0,5 → 0,3 s | 0,015 → 0,015 | 0 → 0 ms | [antes](audit/before/website/application/01-application-desktop.png), [final Fix 3](audit/after/website/application/01-application-desktop-fix3.png) |
| Website `/application.html` | Móvil | 100/100/100/54 → 100/100/100/54 | 1,1 → 0,9 s | 0,03 → 0,029 | 30 → 20 ms | [antes](audit/before/website/application/01-application-mobile.png), [final Fix 3](audit/after/website/application/01-application-mobile-fix3.png) |

## 4. Fixes de rendimiento

### Fix 1: reservar espacio en incidencias

- **Problema y causa:** los estados de carga de `IncidentSummary` y `IncidentList` ocupaban menos espacio que el resumen y las tarjetas finales, desplazando el contenido al llegar los datos.
- **Cambio:** esqueletos de altura y estructura aproximadas al contenido final, manteniendo accesibilidad. Archivos: [incident-summary.tsx](uis/backoffice/components/incident-summary.tsx) y [incident-list.tsx](uis/backoffice/components/incident-list.tsx).
- **Medición:** escritorio Performance 77 → 100, CLS 0,662 → 0,026; móvil Performance 90 → 100, CLS 0,21 → 0,049. LCP y TBT quedaron iguales a la línea base.
- **Commit:** [Reservar espacio en incidencias para reducir CLS](https://github.com/miio3689/ai-engineering-company-project-monorepo/commit/db6626666a64e63e57b69ae8833fea86b9ee9a78).
- **Capturas:** [escritorio](audit/after/backoffice/incidents-list/01-incidents-list-desktop-fix1.png), [móvil](audit/after/backoffice/incidents-list/01-incidents-list-mobile-fix1.png).

### Fix 2: imágenes optimizadas del home

- **Problema y causa:** las imágenes de Unsplash se servían con un ancho único y la imagen hero carecía de prioridad y pista de precarga responsiva, demorando su descarga en móvil.
- **Cambio:** `srcset`/`sizes`, dimensiones intrínsecas, `fetchpriority="high"`, preload y preconnect para el hero; carga diferida y dimensiones para la imagen secundaria. Archivo: [index.html](uis/website/index.html).
- **Medición:** home móvil Performance 95 → 100 y LCP 2,9 → 1,1 s; CLS 0,036 sin cambio. Escritorio Performance 100 → 100 y LCP 0,7 → 0,6 s; el CLS pasó de 0,032 a 0,045, una variación pequeña que sigue en verde y que probablemente sea ruido de medición, no una mejora. El ahorro estimado de imagen de Lighthouse en escritorio pasó de 164 KiB a 68 KiB.
- **Commit:** [Imágenes optimizadas del home para reducir LCP](https://github.com/miio3689/ai-engineering-company-project-monorepo/commit/42dd207df5a16593297fa17a293e68afdc20da9d).
- **Capturas:** [escritorio Fix 2](audit/after/website/home/01-home-desktop-fix2.png), [móvil Fix 2](audit/after/website/home/01-home-mobile-fix2.png).

### Fix 3: CSS Tailwind compilado

- **Problema y causa:** las páginas generaban CSS en el navegador mediante el script síncrono `cdn.tailwindcss.com` y duplicaban la configuración inline del tema.
- **Cambio:** Tailwind v3 se compila con PostCSS/Autoprefixer; se centralizó el tema y ambos HTML cargan el CSS emitido por Vite. Archivos: [tailwind.config.js](uis/website/tailwind.config.js), [postcss.config.js](uis/website/postcss.config.js), [styles/tailwind.css](uis/website/styles/tailwind.css), [index.html](uis/website/index.html) y [application.html](uis/website/application.html).
- **Medición:** la puntuación Performance permaneció en 100 en las rutas ya puntuadas. Home: móvil LCP 1,1 → 1,0 s; escritorio LCP 0,6 → 0,6 s y FCP 0,4 → 0,3 s. Formulario: móvil LCP 1,1 → 0,9 s; escritorio 0,5 → 0,3 s. Se eliminó la dependencia runtime de Tailwind CDN y su aviso de producción.
- **Pendiente observado:** siguen apareciendo «Render-blocking requests» (CSS propio y Google Fonts) y «Network dependency tree».
- **Commit:** [Fix 3 - Sustituir Tailwind CDN por CSS compilado en el website](https://github.com/miio3689/ai-engineering-company-project-monorepo/commit/15c19c7481f94ae3134de46a55f6dd223aa53067).
- **Capturas:** [home escritorio Fix 3](audit/after/website/home/01-home-desktop-fix3.png), [home móvil Fix 3](audit/after/website/home/01-home-mobile-fix3.png), [formulario escritorio Fix 3](audit/after/website/application/01-application-desktop-fix3.png), [formulario móvil Fix 3](audit/after/website/application/01-application-mobile-fix3.png).

## 5. Refactor del hook

El **Fix 4** extrae `submittingRef`, `isSubmitting`, el rechazo síncrono de un segundo envío y la liberación en `finally` a `useSubmissionLock`. La validación, los payloads, las llamadas al servicio y los errores específicos permanecen en cada formulario. Afecta solo a `/inventory/orders/inbound` y `/inventory/orders/outbound`; las páginas evaluadas no usan estos formularios, así que no se atribuye efecto Lighthouse.

Verificación registrada: `npm run typecheck`, `npm run lint`, `npm run build` y 18 pruebas existentes de autenticación pasaron. No se añadió test unitario del hook porque montarlo requeriría librerías de test adicionales.

**Commit:** [Fix 4 - Hook:  Extraer useSubmissionLock en los formularios de inventario](https://github.com/miio3689/ai-engineering-company-project-monorepo/commit/0af88c6ecd333f19eb2eb2179fe03b2efcfc17f0).

## 6. Fix de mayor impacto

El Fix 1 produjo el mayor aumento de puntuación: Performance en `/incidents/list` escritorio subió 23 puntos (77 → 100), junto con una bajada de CLS de 0,662 a 0,026. El Fix 2 produjo la mayor reducción de LCP: 2,9 → 1,1 s en la home móvil. Son mejoras en dimensiones distintas y las dos son relevantes.

## 7. No aplicado y limitaciones

- **Contraste y SEO de la home:** no se corrigieron el texto con opacidad que afecta Accesibilidad 96 ni la meta description duplicada.
- **SEO 54–60:** no se determinó el motivo exacto. El entorno de Codespaces podría influir, pero no se afirma como causa verificada.
- **Scripts clásicos:** `lang.js` y `alidation.js` aún generan avisos de Vite durante el build.
- **Dependencias:** `npm install` en website reportó dos vulnerabilidades, una moderada y una alta; no se trataron por estar fuera de alcance.
- **Terceros y red:** Google Fonts sigue siendo un recurso externo asociado a render-blocking. En escritorio continúan «LCP request discovery» y «Improve image delivery» (68 KiB estimados), aunque el LCP quedó en 0,6 s.
- **Métricas no cubiertas:** no se midieron TTFB ni INP. Codespaces añade latencia de reenvío de puertos; las mediciones son comparables entre sí, no directamente con local.
- **Refactor:** el hook no tiene prueba unitaria propia.
- **Skills:** las skills de agente opcionales del ticket no se instalaron.
- **Productos:** no se tomó captura nueva de `/inventory/products`; las páginas no fueron modificadas por estos fixes. Se conservan las capturas iniciales como referencia, sin copiarlas a `audit/after/`.

## 8. Siguientes pasos recomendados

1. Corregir el contraste de la home y eliminar la descripción duplicada; volver a medir Accesibilidad y SEO.
2. Revisar la entrega de Google Fonts y el CSS propio que Lighthouse marca como render-blocking, midiendo por separado el impacto.
3. Investigar los 68 KiB de imagen restantes y «LCP request discovery» en escritorio antes de nuevos cambios.
4. Determinar, con auditorías detalladas por URL, la causa concreta del SEO 54–60; evitar atribuciones basadas solo en la puntuación.
5. Añadir una prueba automatizada de `useSubmissionLock` únicamente si se incorpora una infraestructura de pruebas de hooks sin ampliar dependencias fuera del plan acordado.
