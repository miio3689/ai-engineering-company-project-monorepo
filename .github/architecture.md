# Architecture

## Objetivo

Este documento describe la estructura del proyecto y la responsabilidad de cada directorio y archivo.

La arquitectura está organizada siguiendo el principio de **una única responsabilidad por archivo**, facilitando el mantenimiento, la reutilización del código y su escalabilidad.

---

## Estructura del proyecto

```text
src/
├── types/
│   └── models.ts
│
├── utils/
│   ├── collections.ts
│   ├── search.ts
│   ├── transformations.ts
│   └── validations.ts
│
└── index.html (opcional)
```

---

## Directorios

### `types/`

Contiene todas las interfaces, tipos y enumeraciones utilizadas por la aplicación.

No debe contener:

* Lógica de negocio.
* Validaciones.
* Cálculos.
* Funciones de utilidad.

#### Archivo

##### `models.ts`

Responsable de definir:

* Interfaces.
* Tipos (`type`).
* Enumeraciones mediante *union types*.

---

### `utils/`

Contiene toda la lógica de negocio del proyecto.

Cada archivo debe tener una responsabilidad específica.

---

## Archivos

### `collections.ts`

Responsabilidad:

Gestionar operaciones sobre colecciones de datos.

#### Debe contener

* Funciones de filtrado.
* Funciones de ordenación.
* Operaciones sobre arrays.

#### No debe contener

* Cálculos financieros.
* Validaciones.
* Búsquedas binarias o lineales.
* Interfaces.

---

### `search.ts`

Responsabilidad:

Implementar algoritmos de búsqueda.

#### Debe contener

* Búsqueda lineal.
* Búsqueda binaria.

#### No debe contener

* Ordenaciones.
* Validaciones.
* Transformaciones.
* Interfaces.

---

### `transformations.ts`

Responsabilidad:

Realizar transformaciones, cálculos y generación de métricas.

#### Debe contener

* Cálculos financieros.
* Conversión de monedas.
* Agregaciones.
* Reportes.
* Rankings.
* Métricas de rendimiento.

#### No debe contener

* Interfaces.
* Validaciones.
* Operaciones de búsqueda.

---

### `validations.ts`

Responsabilidad:

Validar las reglas de negocio de las entidades.

#### Debe contener

* Validaciones de `MenuItem`.
* Validaciones de `SaleTransaction`.
* Validaciones de `Location`.

#### No debe contener

* Cálculos.
* Agregaciones.
* Ordenaciones.
* Interfaces.

---

### `index.html` (opcional)

Página sencilla para realizar pruebas manuales durante el desarrollo.

Puede utilizarse para:

* Ejecutar funciones.
* Mostrar resultados.
* Verificar el comportamiento de la lógica implementada.

No forma parte de la lógica principal del proyecto.

---

## Flujo de dependencias

La arquitectura debe respetar el siguiente flujo:

```text
models.ts
      │
      ▼
collections.ts
search.ts
transformations.ts
validations.ts
      │
      ▼
Aplicación / pruebas
```

Los archivos de utilidades utilizan los modelos definidos en `models.ts`, pero nunca deben depender entre sí de forma innecesaria.

---

## Principios de arquitectura

La implementación debe seguir los siguientes principios:

* Una única responsabilidad por archivo.
* Bajo acoplamiento entre módulos.
* Alta cohesión dentro de cada archivo.
* Código reutilizable.
* Funciones independientes.
* Tipado estricto.
* Separación clara entre modelos y lógica de negocio.

---

## Organización futura

Si el proyecto crece, la estructura deberá mantenerse organizada por responsabilidades.

Ejemplo:

```text
src/
├── types/
├── utils/
├── services/
├── helpers/
├── constants/
├── data/
└── tests/
```

La incorporación de nuevos directorios no debe romper la separación de responsabilidades existente.

---

## Objetivo final

La arquitectura debe facilitar que cualquier desarrollador pueda localizar rápidamente la lógica correspondiente a cada funcionalidad, mantener el código de forma sencilla y ampliar el proyecto sin generar dependencias innecesarias entre módulos.
