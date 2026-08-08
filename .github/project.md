# Project

## Objetivo

Desarrollar el frontend del sistema **Talent Pipeline Tracker**, una herramienta interna utilizada por el departamento de **People & Talent** de Brasaland para gestionar el proceso de selección de candidatos.

La aplicación permitirá visualizar, buscar, filtrar y administrar candidaturas de forma eficiente utilizando una API REST ya existente.

---

## Contexto

Brasaland es una cadena de restaurantes con presencia en Colombia y Estados Unidos que se encuentra en pleno proceso de transformación digital mediante el equipo **Brasaland Digital**.

El departamento de People & Talent gestiona actualmente las candidaturas mediante hojas de cálculo compartidas y documentos independientes, lo que provoca pérdidas de información, errores de sincronización y una gestión poco eficiente.

Este proyecto sustituirá ese proceso manual por una aplicación web moderna que centralice toda la información de los candidatos.

---

## Usuarios

La aplicación está destinada al equipo interno de **People & Talent** de Brasaland.

Los usuarios utilizarán la herramienta para:

* Consultar todas las candidaturas.
* Buscar candidatos rápidamente.
* Filtrar candidaturas por estado y etapa.
* Consultar el detalle de cada candidato.
* Actualizar el estado del proceso de selección.
* Añadir y eliminar notas internas.
* Registrar nuevas candidaturas.
* Editar información existente.

---

## Objetivos funcionales

La aplicación deberá permitir:

* Visualizar todas las candidaturas en un listado.
* Buscar candidatos por nombre o correo electrónico.
* Filtrar por estado y etapa del proceso.
* Consultar el detalle completo de un candidato.
* Actualizar el estado y la etapa de una candidatura.
* Crear nuevas candidaturas.
* Editar candidaturas existentes.
* Gestionar notas internas asociadas a cada candidato.
* Comunicar claramente los estados de carga y los posibles errores durante las operaciones.

---

## Tecnologías

El proyecto se desarrollará utilizando:

* Next.js (App Router)
* React
* TypeScript
* Tailwind CSS
* ESLint

La comunicación con el backend se realizará mediante una API REST utilizando peticiones HTTP asíncronas.

---

## Integración

La aplicación consumirá la API proporcionada por el equipo backend.

La URL base de la API se almacenará mediante variables de entorno para facilitar la configuración entre distintos entornos.

---

## Calidad del proyecto

La implementación deberá priorizar:

* Código modular y reutilizable.
* Componentes reutilizables.
* Tipado estricto con TypeScript.
* Separación clara entre presentación, lógica y acceso a datos.
* Experiencia de usuario fluida.
* Interfaz rápida y reactiva.
* Manejo adecuado de estados de carga y errores.

---

## Alcance

Este proyecto comprende exclusivamente el desarrollo del frontend.

No se implementará lógica de backend ni persistencia propia, ya que toda la información será gestionada mediante la API existente.

---

## Resultado esperado

El resultado será una aplicación web interna que permita al equipo de People & Talent gestionar de forma eficiente todo el ciclo de vida de las candidaturas desde una única interfaz, mejorando la organización, reduciendo errores y agilizando el proceso de selección.
