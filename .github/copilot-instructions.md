# Instrucciones de Copilot

## Estructura y Semántica HTML

- El HTML usa etiquetas semánticas apropiadas en lugar de contenedores genéricos.
- Todas las imágenes tienen atributos `alt` descriptivos.
- Los formularios usan `label` correctamente asociados con `input`.
- El marcado [Schema.org](http://schema.org/) está presente y correctamente implementado.
- La estructura del documento es lógica y jerárquica.

## Diseño Responsive y Tailwind

- El sitio es completamente responsive y se adapta a móvil, tablet y escritorio.
- Existe un comando documentado y funcional, compatible con Codespaces, para ejecutar el proyecto localmente con `npx`.
- Se usa diseño mobile-first.
- Todos los estilos usan clases utilitarias de Tailwind.
- Los breakpoints de Tailwind (`sm:`, `md:`, `lg:`) se usan apropiadamente.
- No hay CSS personalizado innecesario; solo Tailwind.
- El diseño es visualmente coherente y profesional.
- El rendimiento tiene que puntuar mínimo 80.

## Accesibilidad

- Todos los elementos interactivos son accesibles por teclado.
- Los atributos ARIA se usan donde mejoran la accesibilidad.
- El contraste de colores cumple con estándares mínimos.
- La navegación es lógica y predecible.
- Los mensajes de error son anunciados apropiadamente.

## Formulario y Validación

- Todos los campos especificados en [CONTEXT.md](../CONTEXT.md) están presentes.
- Los tipos de `input` son apropiados para cada campo.
- La validación con JavaScript funciona correctamente para todos los campos.
- Los mensajes de error son específicos y útiles, no solo "campo inválido".
- La validación previene el envío de datos incorrectos.
- Los estados visuales del formulario son claros: foco, error y éxito.
- El botón de limpiar formulario funciona correctamente.

## Adherencia al Contexto

- La landing page refleja fielmente el tipo de empresa y sector especificado en [CONTEXT.md](../CONTEXT.md).
- El contenido presenta la experiencia y ventajas competitivas de la empresa.
- Los campos del formulario coinciden exactamente con los requeridos en [CONTEXT.md](../CONTEXT.md).
- Cualquier regla de validación específica del dominio está implementada.
- El tono y contenido son coherentes con una empresa establecida que se digitaliza.