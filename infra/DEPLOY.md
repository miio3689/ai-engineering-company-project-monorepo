# Despliegue de Brasaland en un VPS

Guía para Ubuntu 22.04 con acceso por IP y HTTP. El Compose de producción es
un **override** del Compose base: desde la raíz del repositorio se usan siempre
ambos archivos, en este orden:

```sh
docker compose -f docker-compose.yml -f docker-compose.prod.yml ...
```

## Requisitos

- VPS DigitalOcean con Ubuntu 22.04 y una IP pública estática.
- Acceso SSH con permisos `sudo`.
- Recomendado: al menos 2 vCPU y 4 GB de RAM; la interfaz ejecuta servidores
  de desarrollo de Next.js y Vite.
- Git para clonar el repositorio y acceder a la rama `docker`.
- Puertos 3000 (website), 3001 (backoffice) y 8000 (API) disponibles en el host.
  No se usa un dominio ni HTTPS.
- Docker Engine, el plugin oficial Docker Compose, `curl`, `openssl` y `tar`.

El Compose base usa `env_file` con `required: false`, opción disponible desde
Docker Compose **2.24.0**, y `build.additional_contexts`, disponible desde
Docker Compose **2.17.0**. Por tanto, la versión mínima para este proyecto es
**Docker Compose 2.24.0**. Verifica `docker compose version` y actualiza el
plugin desde el repositorio oficial si es anterior.

Referencias: [env_file en Docker Compose](https://docs.docker.com/reference/compose-file/services/#env_file)
y [`additional_contexts`](https://docs.docker.com/reference/compose-file/build/#additional_contexts).

## 1. Instalar Docker Engine

En Ubuntu 22.04, sigue el procedimiento oficial de Docker: configura el
repositorio APT de Docker, instala Engine y el plugin Compose desde ese
repositorio (no desde paquetes de terceros):

```sh
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Verifica la instalación:

```sh
sudo docker --version
sudo docker compose version
sudo docker run --rm hello-world
```

Los comandos de esta guía usan `sudo`; si configuras el grupo `docker`, ten en
cuenta que pertenecer a él concede privilegios equivalentes a root.

## 2. Clonar la rama de despliegue

En el VPS, clona el repositorio directamente en la rama `docker`:

```sh
git clone --branch docker https://github.com/miio3689/ai-engineering-company-project-monorepo.git brasaland
cd brasaland
```

## 3. Crear el `.env` de producción en el VPS

La plantilla `.env.production.example` sirve como referencia, pero no se carga
automáticamente. En la raíz del clon crea `.env` en el propio servidor (por
ejemplo, `nano .env`) y limita sus permisos con `chmod 600 .env`. No lo añadas
al repositorio ni uses secretos de ejemplo. Genera `JWT_SECRET_KEY` en el VPS
con `openssl rand -hex 32` y pega directamente el resultado en el archivo; no
copies la clave a documentación, chat o repositorio.

| Variable | Para qué sirve | Valor de ejemplo |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | URL del API que usa el navegador. | `http://203.0.113.10:8000` |
| `CORS_ALLOWED_ORIGINS` | Orígenes web permitidos por el API; incluye el origen del backoffice y, si llama al API, el del website. | `http://203.0.113.10:3001,http://203.0.113.10:3000` |
| `FRONTEND_BASE_URL` | Origen del backoffice usado para construir enlaces de restablecimiento. | `http://203.0.113.10:3001` |
| `VITE_ALLOWED_HOSTS` | Host permitido por Vite para el sitio web. | `203.0.113.10` |
| `API_INTERNAL_URL` | URL interna que usa Next.js para hablar con el servicio API. | `http://api:8000` (valor predeterminado) |
| `WATCH_POLLING` | Controla el polling de los watchers en desarrollo. En producción se fuerza a `false`. | `false` |
| `JWT_SECRET_KEY` | Clave de firma JWT; obligatoria, mínimo 32 caracteres. | Generada en el VPS con `openssl rand -hex 32`; no usar un literal de ejemplo. |
| `DATABASE_URL` | Conexión SQL opcional para los endpoints de inventario. | Vacío si no se configura; el inventario no estará disponible. |
| `RESEND_API_KEY` | Clave opcional de Resend para enviar correos de recuperación. | Vacío si no se configura; no se enviarán esos correos. |
| `BACKOFFICE_PORT` | Puerto del host publicado para el backoffice; dentro del contenedor Next.js escucha en 3000. | `3001` |
| `WEBSITE_PORT` | Puerto del host publicado para el website; dentro del contenedor Vite escucha en 5174. | `3000` |
| `API_ENV_FILE` | Ruta del archivo de variables para el API; opcional, por defecto `./.env`. | `./.env` |
| `UIS_ENV_FILE` | Ruta del archivo de variables para las interfaces; opcional, por defecto `./.env`. | `./.env` |
| Puerto del API | Puerto público fijo del servicio API; no hay variable configurable en Compose. | `8000` |

El mapeo host→contenedor es `3000→5174` para website y `3001→3000` para
backoffice. La API permanece en `8000→8000`. `CORS_ALLOWED_ORIGINS` debe
incluir el origen del backoffice en `:3001`; `FRONTEND_BASE_URL` debe apuntar
a ese mismo origen para los enlaces de recuperación.

`203.0.113.10` es una IP reservada para documentación: reemplázala por la IP
pública del VPS. `CORS_ALLOWED_ORIGINS` debe contener solo los orígenes que
usarás, incluidos esquema y puerto, sin barra final. `API_INTERNAL_URL` usa el
nombre DNS interno de Compose, no una IP pública. Aunque el archivo se comparte
como `env_file` del API y `uis`, el override deja vacías dentro de `uis` las
variables `JWT_SECRET_KEY`, `RESEND_API_KEY` y `DATABASE_URL`.

Arranca el stack:

```sh
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## 4. Verificar el despliegue

```sh
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
curl -fsS -o /dev/null -w 'website: %{http_code}\n' http://203.0.113.10:3000/
curl -fsS -o /dev/null -w 'backoffice: %{http_code}\n' http://203.0.113.10:3001/
curl -fsS -o /dev/null -w 'api: %{http_code}\n' http://203.0.113.10:8000/docs
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml exec uis \
  wget -qO- http://api:8000/docs >/dev/null \
  && echo 'uis -> api por nombre de servicio: OK'
```

Los cuatro `curl` deben informar `200`; el último comando comprueba la resolución
del servicio `api` en la red privada de Compose desde `uis`. La IP de estos
comandos también es un marcador documental y debe reemplazarse.

## 5. Firewall y puertos públicos

En el VPS revisado, UFW no está activo y no hay acceso al panel de firewall del
proveedor. Los puertos TCP **3000**, **3001** y **8000** ya se comprobaron
accesibles desde Internet. Docker publica puertos mediante reglas que pueden
saltarse las reglas de UFW, así que UFW inactivo no filtra estas publicaciones.
No abras 443: este despliegue no incluye TLS. Limita la exposición con un
firewall de proveedor cuando haya acceso disponible y permite solo los orígenes
necesarios.

## Operación

Actualizar desde la rama de despliegue:

```sh
git pull --ff-only
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Ver logs o reiniciar:

```sh
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml restart
```

Parar el stack sin borrar sus datos:

```sh
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml down
```

Los almacenes TinyDB `services/api/auth.json`, `services/api/incidents.json` y
`services/api/suppliers.json` se escriben en el VPS gracias al bind mount
heredado `./services:/app/services`. Para hacer una copia coherente, detén el
API y archiva los JSON que ya existan; los datos de autenticación son sensibles,
así que restringe y cifra también la copia:

```sh
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml stop api
tar -czf "$HOME/brasaland-tinydb-$(date +%F-%H%M%S).tar.gz" \
  services/api/auth.json services/api/incidents.json services/api/suppliers.json
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml start api
```

## LIMITACIONES

- Solo HTTP por IP; no hay dominio ni HTTPS.
- `next dev` y `vite` son servidores de desarrollo y no son una arquitectura de
  producción endurecida.
- TinyDB se persiste mediante un bind mount en el árbol del repositorio; no es
  una base de datos gestionada ni ofrece por sí sola alta disponibilidad.
- Los contenedores ejecutan sus procesos como root.
- Mejoras futuras: configurar dominio y HTTPS mediante un proxy inverso,
  generar builds de producción para Next.js/Vite, ejecutar los procesos con
  usuarios no root y asegurar el acceso SSH con claves en lugar de contraseñas.
