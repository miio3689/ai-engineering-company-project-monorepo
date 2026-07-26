# Project

## Objetivo

Este documento describe el alcance y los objetivos del proyecto correspondiente al **Hito 2: Fundamentos de Programación**.

El propósito de este hito es desarrollar la capa de lógica de negocio que servirá como base para los futuros sistemas internos de Brasaland. La implementación debe ser completamente reutilizable, estar desarrollada en TypeScript y seguir buenas prácticas de programación.

---

## Descripción del proyecto

Brasaland Digital necesita desarrollar una colección de utilidades que permitan procesar la información operativa de la empresa de forma eficiente.

Estas utilidades serán utilizadas posteriormente por aplicaciones internas, dashboards y herramientas de análisis, por lo que deben ser fiables, reutilizables y fáciles de mantener.

En este hito el foco está exclusivamente en la lógica de programación y el tratamiento de datos.

---

## Alcance

El proyecto debe incluir el desarrollo de:

* Modelado de datos mediante interfaces TypeScript.
* Operaciones sobre colecciones de datos.
* Algoritmos de búsqueda.
* Transformaciones y agregaciones de datos.
* Cálculos financieros.
* Cálculo de métricas de rendimiento.
* Validaciones de reglas de negocio.

---

## Fuera del alcance

Este proyecto **no debe incluir**:

* Inteligencia Artificial.
* Backend.
* Bases de datos.
* APIs externas.
* Autenticación o autorización.
* Persistencia de información.
* Frameworks frontend para implementar la lógica.
* Funcionalidades que no formen parte del briefing.

---

## Tecnologías

Las tecnologías utilizadas en este proyecto serán:

* TypeScript
* JavaScript (ES6+)
* HTML (opcional para pruebas)
* Tailwind CSS (opcional para pruebas visuales)

No deben utilizarse librerías externas para implementar la lógica solicitada, salvo que el proyecto lo indique expresamente.

---

## Funcionalidades

El proyecto debe proporcionar utilidades para trabajar con la información de Brasaland.

### Gestión de colecciones

* Filtrar elementos.
* Ordenar colecciones.
* Buscar registros.
* Agrupar información.

### Transformación de datos

* Calcular ingresos.
* Calcular márgenes.
* Convertir monedas.
* Calcular costes.
* Obtener medias.
* Generar rankings.
* Crear reportes agregados.

### Validaciones

* Validar entidades de negocio.
* Comprobar reglas de negocio.
* Detectar datos inválidos.
* Generar mensajes de error descriptivos.

---

## Estructura del proyecto

El código debe organizarse por responsabilidades.

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

Cada archivo debe contener únicamente las funciones relacionadas con su responsabilidad.

---

## Objetivos de calidad

Toda la implementación debe cumplir los siguientes principios:

* Utilizar TypeScript con tipado estricto.
* Escribir funciones puras siempre que sea posible.
* Evitar efectos secundarios.
* No modificar los parámetros recibidos, salvo que se indique expresamente.
* Utilizar nombres descriptivos para variables, funciones e interfaces.
* Mantener una única responsabilidad por función.
* Escribir código reutilizable y fácil de mantener.
* Priorizar la legibilidad sobre soluciones excesivamente complejas.

---

## Criterios de aceptación

El proyecto se considerará completo cuando:

* Todas las interfaces estén correctamente definidas.
* Todas las funciones solicitadas estén implementadas.
* Las validaciones respeten las reglas de negocio.
* Los cálculos financieros sean correctos tanto en USD como en COP.
* Las funciones manejen correctamente casos límite.
* Las operaciones de ordenación no modifiquen los arrays originales.
* Todo el código compile sin errores de TypeScript.

---

## Resultado esperado

Al finalizar este hito, el proyecto dispondrá de una biblioteca de utilidades TypeScript capaz de gestionar, transformar, validar y analizar la información operativa de Brasaland.

Esta capa de lógica será la base sobre la que se construirán los siguientes módulos del sistema interno de la empresa.
