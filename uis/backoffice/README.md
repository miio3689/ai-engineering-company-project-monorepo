This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## Autenticación (AUTH-02)

- `/login` envía `POST /auth/login` como
  `application/x-www-form-urlencoded`, con `username=email` y `password`.
- `/register` envía JSON a `POST /users`, sin token, y después inicia sesión
  automáticamente. Incluye email, contraseña y nombre/teléfono/dirección
  opcionales. Si se indica teléfono o dirección, la API exige nombre.
- Ambos flujos guardan el `access_token` devuelto en la clave `access_token`
  de `localStorage` y redirigen a `/` (Talent Pipeline Tracker).
- Los errores 409 por email duplicado y los errores 422 de validación se
  muestran junto al campo correspondiente. Si la cuenta se crea pero falla
  el login automático, se indica que hay que usar `/login`, sin repetir el alta.

`services/api-client.ts` centraliza las peticiones de candidaturas, proveedores
e incidencias. En el navegador lee el token antes de cada petición y añade
`Authorization: Bearer <token>`. Un 401 protegido elimina el token y navega a
`/login`; las peticiones públicas de login/registro no llevan token ni activan
esta redirección.

El layout raíz envuelve las rutas con `components/auth-guard.tsx`, un guard
exclusivamente cliente. Solo `/login` y `/register` son públicas; cualquier
otra ruta, incluidas las candidaturas por ID y las nuevas vistas internas,
requiere un token no vacío. Durante SSR e hidratación se muestra
«Comprobando sesión…», sin montar el contenido protegido. Si falta el token,
se usa `router.replace("/login")`; si el almacenamiento está bloqueado, se
muestra un error explícito sin revelar la vista. Se vuelve a comprobar al
cambiar de ruta, recuperar el foco, restaurar la página o recibir cambios
de almacenamiento desde otra pestaña. Las vistas públicas siguen accesibles
incluso con sesión iniciada.

No hay middleware ni comprobación local de la firma/caducidad: la API valida
el token y el cliente conserva el manejo de 401. El guard evita mostrar las
vistas en el navegador; no sustituye la autorización del backend ni evita la
ejecución o serialización de componentes de servidor de Next.js.

Los componentes de servidor existentes no tienen acceso a `localStorage`.
No se cambia su modelo de carga en esta tarea. Además, `services/api` no
implementa `/records`, que consume el Tracker: la redirección a `/` funciona,
pero mostrar candidaturas requiere disponer de ese backend.

Usar la misma `NEXT_PUBLIC_API_BASE_URL` y los comandos de API/Next.js
documentados abajo. Para simular logout manual en las herramientas de
desarrollo del navegador:

```js
localStorage.removeItem("access_token");
```

Pruebas de regresión del cliente, contratos y validación (Node.js >= 22.15,
sin dependencias adicionales a las del proyecto):

```bash
cd uis/backoffice
npm run test:auth
npm run typecheck
```

## Gestión de cuenta

`/account/profile` queda bajo el guard cliente existente. Carga email y perfil
con `GET /auth/me` a través del cliente API centralizado; el email es solo de
lectura. Permite editar nombre, teléfono y dirección con `PUT /profiles/me`,
mostrando la respuesta guardada inmediatamente, confirmación y errores
legibles. Los campos opcionales vacíos se envían como `null`; restablecer
recupera los últimos valores guardados. La carga fallida permite reintentar.

Si `/auth/me` devuelve `profile: null`, se muestra el email y se informa de que
hay que contactar con la administración: `PUT /profiles/me` no crea perfiles.
No se intenta un alta con un endpoint inexistente.

La navegación compartida de las vistas internas incluye «Mi perfil» y
«Cerrar sesión». Logout elimina `access_token`, notifica al guard existente
y reemplaza el documento por `/login`, descartando la caché en memoria del
router. Al volver atrás, el guard vuelve a comprobar la sesión. No se cambia
el guard ni se añade middleware. El cierre es local: no revoca el JWT en la
API, que conserva su caducidad normal.

## Directorio de proveedores

La ruta `/suppliers`, enlazada desde el listado principal, permite consultar
proveedores y filtrar por país y categoría. Los filtros se combinan con AND y
consultan de nuevo la API sin recargar la página. Incluye estados de carga,
error con reintento y listado vacío.

El formulario permite dar de alta proveedores con varias categorías y los
campos opcionales de contacto/notas. Comprueba nombre, categorías, tarifa
positiva, correo opcional y correspondencia país/moneda antes de enviar.
Los errores 422 se presentan como mensajes legibles y se conservan los datos
para corregirlos. Incluye un botón para limpiar el formulario.

Cada fila permite editar la tarifa y activar/suspender al proveedor.
Las respuestas de POST/PATCH actualizan el listado y sus badges sin recargar
la página ni cambiar los filtros: un alta solo se muestra si coincide con los
filtros seleccionados. No existe acción de eliminación en la interfaz.

Desde la raíz del monorepo, ejecutar en dos terminales:

```bash
# API (con la base de proveedores ya sembrada)
uv run uvicorn services.api.app.main:app --host 0.0.0.0 --port 8000
```

```bash
cd uis/backoffice
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npx next dev --hostname 0.0.0.0 --port 3000
```

En Codespaces, usar como `NEXT_PUBLIC_API_BASE_URL` la URL HTTPS del puerto
8000 reenviado, accesible desde el navegador. El origen del frontend debe estar
permitido por CORS en la API. Esta variable se incorpora al código cliente al
arrancar/compilar Next.js; reiniciar el frontend después de cambiarla.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
