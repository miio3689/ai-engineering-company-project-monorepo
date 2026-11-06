# `uis` folder

This folder contains **all the user interfaces** related to the company for the cross-functional AI Engineering project (for example: web applications, internal dashboards, customer portals, Streamlit/Gradio apps, etc.).

Each subfolder inside `uis/` must correspond to **one specific user interface** (for example: `website`, `backoffice`) and include its own technical and functional documentation.

- **Main purpose**: to centralize in a single place all the frontend applications that support the company's use cases.
- **Recommendation**: document in this file (or in sub-READMEs) the applications you add, their objective, the technology used, and how to run them.

## Development container

The Dockerfile in this folder runs the public Vite website on port `5174` and the Next.js backoffice on port `3000`. The existing backoffice configuration is preserved; its port is not changed to `3001`.

From `uis/`, build and run both interfaces with:

```bash
docker build -t brasaland-uis .
docker run --rm -p 5174:5174 -p 3000:3000 brasaland-uis
```

> _Spanish version: [README.es.md](./README.es.md)._
