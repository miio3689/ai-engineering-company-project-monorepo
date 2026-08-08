# Architecture

## Objetivo

Este documento describe la estructura del proyecto y la responsabilidad de cada directorio y archivo.

La arquitectura está organizada siguiendo el principio de **una única responsabilidad por carpeta y componente**, facilitando el mantenimiento, la reutilización del código y su escalabilidad.

---

## Estructura del proyecto

```text
app/
├── page.tsx
├── candidates/
│   └── [id]/
│       └── page.tsx
│
├── components/
│
├── types/
│   └── models.ts
│
├── services/
│   └── api.ts
│
├── hooks/ (opcional)
│
├── lib/ (opcional)
│
└── public/
```

---

## Directorios

### `app/`

Contiene todas las páginas de la aplicación utilizando **Next.js App Router**.

Cada ruta representa una vista de la aplicación.

No debe contener:

* Lógica compleja de negocio.
* Acceso directo a la API.
* Definición de modelos.

---

### `components/`

Contiene todos los componentes reutilizables de la interfaz.

Debe incluir únicamente componentes de presentación o componentes reutilizables entre distintas páginas.

No debe contener:

* Lógica de acceso a datos.
* Modelos TypeScript.
* Configuración de la aplicación.

---

### `types/`

Contiene todas las interfaces, tipos y enumeraciones utilizadas por la aplicación.

No debe contener:

* Lógica de negocio.
* Peticiones HTTP.
* Componentes React.

#### Archivo

##### `models.ts`

Responsable de definir:

* Interfaces.
* Tipos (`type`).
* Enumeraciones mediante *union types*.

---

### `services/`

Contiene toda la comunicación con la API.

Debe centralizar:

* Peticiones GET.
* Peticiones POST.
* Peticiones PUT.
* Peticiones PATCH.
* Peticiones DELETE.

No debe contener:

* Componentes React.
* Lógica de presentación.

---

### `hooks/` (opcional)

Contiene hooks personalizados reutilizables.

Puede utilizarse para encapsular:

* Obtención de datos.
* Gestión de estados.
* Lógica compartida entre componentes.

No debe contener:

* Componentes visuales.
* Definición de modelos.

---

### `lib/` (opcional)

Contiene utilidades reutilizables que no pertenecen directamente a ningún componente o servicio.

Puede incluir:

* Funciones auxiliares.
* Formateadores.
* Conversores.
* Constantes compartidas.

---

## Rutas principales

### `/`

Responsabilidad:

Mostrar el listado completo de candidaturas.

Debe permitir:

* Buscar candidatos.
* Filtrar por estado.
* Filtrar por etapa.
* Navegar al detalle de cada candidatura.

---

### `/candidates/[id]`

Responsabilidad:

Mostrar toda la información de un candidato.

Debe permitir:

* Consultar los datos completos.
* Actualizar estado.
* Actualizar etapa.
* Gestionar notas.
* Editar la candidatura.

---

## Flujo de dependencias

La arquitectura deberá respetar el siguiente flujo:

```text
models.ts
      │
      ▼
services/
      │
      ▼
hooks/ (opcional)
      │
      ▼
components/
      │
      ▼
app/
```

Los modelos son la base de toda la aplicación.

Los servicios consumen la API.

Los hooks reutilizan la lógica cuando sea necesario.

Los componentes construyen la interfaz.

Las páginas ensamblan todos los elementos anteriores.

---

## Principios de arquitectura

La implementación deberá seguir los siguientes principios:

* Una única responsabilidad por carpeta y archivo.
* Bajo acoplamiento entre módulos.
* Alta cohesión.
* Componentes reutilizables.
* Separación entre interfaz, lógica y acceso a datos.
* Tipado estricto con TypeScript.
* Comunicación con la API centralizada.
* Arquitectura escalable y mantenible.

---

## Organización futura

Si el proyecto crece, la estructura podrá ampliarse manteniendo la separación de responsabilidades.

Ejemplo:

```text
app/
components/
types/
services/
hooks/
lib/
constants/
styles/
tests/
```

La incorporación de nuevos directorios no deberá romper la arquitectura existente.

---

## Objetivo final

La arquitectura debe facilitar que cualquier desarrollador pueda localizar rápidamente cada funcionalidad, mantener el código de forma sencilla y ampliar la aplicación sin generar dependencias innecesarias entre módulos.
