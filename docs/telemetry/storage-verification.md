# Verificación end-to-end del almacenamiento de telemetría

Pasos para repetir la comprobación:

1. Arrancar la API con la conexión a Supabase y el frontend sin cambios (misma `NEXT_PUBLIC_TELEMETRY_ENDPOINT`).
2. Generar eventos reales en el backoffice: un login fallido (técnico), navegación entre pantallas, una orden de entrada y una de salida (negocio).
3. Consultar la tabla en el SQL Editor de Supabase:

       select "timestamp", service, event_type, level, value, message, tags
       from public.telemetry_events
       order by "timestamp" desc
       limit 20;

4. Comprobar que el índice GIN sobre `tags` funciona para búsquedas dentro del JSON:

       select count(*) from public.telemetry_events where tags @> '{"section":"inventory"}';

5. Enviar un lote mixto (eventos válidos e inválidos) a `POST /telemetry/events`. Con 2 eventos válidos, 1 de tipo desconocido y 1 con una propiedad fuera del allowlist, la respuesta debe ser `{"received":4,"stored":2,"rejected":2}`.
6. Confirmar que el frontend no cambió: `git diff main --stat -- uis` no imprime nada.

Resultado: los eventos aparecen con `event_type`, `timestamp` y `tags` correctos; los inválidos se rechazan individualmente sin cancelar el lote.
