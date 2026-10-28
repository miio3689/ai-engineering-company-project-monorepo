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

## Directorio de proveedores

La ruta `/suppliers`, enlazada desde el listado principal, permite consultar
proveedores y filtrar por país y categoría. Los filtros se combinan con AND y
consultan de nuevo la API sin recargar la página. Incluye estados de carga,
error con reintento y listado vacío. Es una pantalla de solo lectura.

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
