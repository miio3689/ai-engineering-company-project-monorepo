# `uis` folder

This folder contains **all the user interfaces** related to the company for the cross-functional AI Engineering project (for example: web applications, internal dashboards, customer portals, Streamlit/Gradio apps, etc.).

Each subfolder inside `uis/` must correspond to **one specific user interface** (for example: `website`, `backoffice`) and include its own technical and functional documentation.

- **Main purpose**: to centralize in a single place all the frontend applications that support the company's use cases.
- **Recommendation**: document in this file (or in sub-READMEs) the applications you add, their objective, the technology used, and how to run them.

## Development container

The Dockerfile runs the public Vite website on container port `5174` and the Next.js backoffice on container port `3000`. With the root Compose file, host ports map as website `3000 -> 5174` and backoffice `3001 -> 3000`; the container ports and `start.sh` remain unchanged.

From `uis/`, build and run both interfaces with:

```bash
docker build -t brasaland-uis .
docker run --rm -p 3000:5174 -p 3001:3000 brasaland-uis
```

## Production builds

For the public website, run these commands from `uis/website/`:

```bash
npm run build
npm run start
```

The website is served on port `5174`.

For the backoffice, run these commands from `uis/backoffice/`:

```bash
NEXT_PUBLIC_API_BASE_URL="https://api.example.com" npm run build
npm run start -- --port 3001
```

`NEXT_PUBLIC_API_BASE_URL` is embedded in the frontend bundle during the build, so set it to the API URL before building.

> _Spanish version: [README.es.md](./README.es.md)._
