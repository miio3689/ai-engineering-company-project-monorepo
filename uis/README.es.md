# Carpeta `uis`

Esta carpeta contiene **todas las interfaces de usuario** relacionadas con la compañía para el proyecto transversal de AI Engineering (por ejemplo: aplicaciones web, dashboards internos, portales de clientes, apps de Streamlit/Gradio, etc.).

Cada subcarpeta dentro de `uis/` debe corresponder a **una interfaz de usuario concreta** (por ejemplo `website`, `backoffice`) e incluir su propia documentación técnica y funcional.

- **Propósito principal**: centralizar en un único lugar todas las aplicaciones frontend que dan soporte a los casos de uso de la compañía.
- **Recomendación**: documenta en este archivo (o en sub-READMEs) las aplicaciones que vayas añadiendo, su objetivo, tecnología usada y cómo ejecutarlas.

## Contenedor de desarrollo

El Dockerfile de esta carpeta ejecuta la web pública con Vite en el puerto `5174` y el backoffice con Next.js en el puerto `3000`. El backoffice conserva su configuración existente; no se cambia a `3001`.

Desde `uis/`, construye y ejecuta ambas interfaces con:

```bash
docker build -t brasaland-uis .
docker run --rm -p 5174:5174 -p 3000:3000 brasaland-uis
```
