# Models

## Objetivo

Este documento define las entidades de negocio utilizadas en el Talent Pipeline Tracker de Brasaland.

Las interfaces describen la estructura de los datos con los que trabajará la aplicación. No contienen reglas de validación ni lógica de negocio; esas se documentan en otros archivos.

Todas las interfaces deberán adaptarse a la especificación oficial de la API.

---

## Candidate

Representa una candidatura registrada en el proceso de selección de Brasaland.

```ts
interface Candidate {
  // Definido según la API
}
```

### Propiedades

La entidad Candidate deberá contener, como mínimo, información relacionada con:

* Identificador único.
* Nombre completo.
* Correo electrónico.
* Teléfono.
* Puesto solicitado.
* Perfil de LinkedIn.
* Enlace al currículum.
* Años de experiencia.
* Estado de la candidatura.
* Etapa del proceso.
* Fecha de aplicación.

La implementación final deberá utilizar exactamente los nombres y tipos definidos por la API.

---

## CandidateNote

Representa una nota interna asociada a una candidatura.

```ts
interface CandidateNote {
  // Definido según la API
}
```

### Propiedades

Como mínimo deberá representar:

* Identificador.
* Identificador del candidato.
* Contenido de la nota.
* Fecha de creación.

La implementación final deberá ajustarse a la estructura proporcionada por la API.

---

## Tipos y enumeraciones

### CandidateStatus

Representa los posibles estados de una candidatura.

```ts
type CandidateStatus =
  | "received"
  | "in_progress"
  | "selected"
  | "discarded";
```

---

### CandidateStage

Representa las etapas del proceso de selección.

```ts
type CandidateStage =
  | "pending"
  | "review"
  | "personal_interview"
  | "technical_interview"
  | "offer_presented";
```

---

## Relaciones entre entidades

Las entidades se relacionan mediante identificadores (`id`), evitando dependencias directas entre objetos.

* Un **Candidate** puede tener múltiples **CandidateNote**.
* Cada **CandidateNote** pertenece únicamente a un **Candidate**.

Las relaciones deberán realizarse utilizando los identificadores definidos por la API.

---

## Observaciones

Los modelos TypeScript deberán mantenerse sincronizados con la documentación oficial de la API.

No deberán añadirse propiedades que no existan en el backend ni omitirse aquellas requeridas por la especificación oficial.
