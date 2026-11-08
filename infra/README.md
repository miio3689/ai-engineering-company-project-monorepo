# `infra` folder

This folder contains **infrastructure configurations** for the monorepo (for example: Dockerfiles, Terraform scripts, deployment manifests, Nginx configs, etc.).

- **Main purpose**: to centralize the definition of the infrastructure required to run the company's applications and services.
- **Recommendation**: document how to provision and deploy the infrastructure.

> _Spanish version: [README.es.md](./README.es.md)._

## Despliegue local y en VPS de Brasaland

Desde la raíz del repositorio, inicia el stack de desarrollo local con:

```sh
docker compose up -d --build
```

Los puertos del host son website `3000` (contenedor `5174`), backoffice `3001`
(contenedor `3000`) y API `8000` (contenedor `8000`). Para requisitos del VPS,
instalación, variables de entorno, verificación y operación, consulta la
[guía de despliegue](./DEPLOY.md). En el VPS, crea `.env` en el servidor y no
lo añadas nunca a Git; después despliega con:

```sh
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### Comunicación entre servicios

Compose conecta los servicios a la red Docker `brasaland`. El servicio de API
se llama `api`; el servidor Next.js se conecta con
`API_INTERNAL_URL=http://api:8000`. Las solicitudes desde el navegador usan
`NEXT_PUBLIC_API_BASE_URL`, que debe contener la URL del API accesible desde el
host.

### Decisiones y limitaciones

- El ticket requiere contenedores de desarrollo: el API base usa `--reload`,
	las aplicaciones usan bind mounts y los procesos se ejecutan como root. El
	override de producción quita `--reload` al API, pero no convierte los
	frontends en builds de producción.
- El VPS se accede por IP y HTTP, sin dominio, proxy inverso ni HTTPS.
- Compose construye las imágenes en el VPS; no se usa un registro de imágenes.
- En esta configuración, las redes Docker personalizadas de GitHub Codespaces
	no tienen salida a Internet. Supabase y el correo se verificaron únicamente
	en el VPS.
- Se modificó `uis/backoffice/services/api-client.ts` para que las solicitudes
	de Next.js desde el servidor usen `API_INTERNAL_URL`; las del navegador
	siguen usando `NEXT_PUBLIC_API_BASE_URL`.
