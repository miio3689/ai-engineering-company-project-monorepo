# Carpeta `uis`

Esta carpeta contiene **todas las interfaces de usuario** relacionadas con la compañía para el proyecto transversal de AI Engineering (por ejemplo: aplicaciones web, dashboards internos, portales de clientes, apps de Streamlit/Gradio, etc.).

Cada subcarpeta dentro de `uis/` debe corresponder a **una interfaz de usuario concreta** (por ejemplo `website`, `backoffice`) e incluir su propia documentación técnica y funcional.

- **Propósito principal**: centralizar en un único lugar todas las aplicaciones frontend que dan soporte a los casos de uso de la compañía.
- **Recomendación**: documenta en este archivo (o en sub-READMEs) las aplicaciones que vayas añadiendo, su objetivo, tecnología usada y cómo ejecutarlas.

## Contenedor de desarrollo

El Dockerfile ejecuta el website público con Vite en el puerto interno `5174` y el backoffice con Next.js en el puerto interno `3000`. Con el Compose de la raíz, los puertos del host son website `3000 -> 5174` y backoffice `3001 -> 3000`; los puertos internos y `start.sh` no cambian.

Desde `uis/`, construye y ejecuta ambas interfaces con:

```bash
docker build -t brasaland-uis .
docker run --rm -p 3000:5174 -p 3001:3000 brasaland-uis
```
