# Business Rules

## Objetivo

Este documento define las reglas de negocio que deben cumplirse durante la gestión del proceso de selección de Brasaland.

Estas reglas son independientes de la implementación y representan las restricciones funcionales del dominio. Todas las validaciones y operaciones de la aplicación deberán respetarlas.

---

## Candidate

### Descripción

Un **Candidate** representa una candidatura registrada en el proceso de selección de Brasaland.

### Reglas de negocio

* Todo candidato debe tener un nombre.
* Todo candidato debe tener un correo electrónico válido.
* El puesto no puede estar vacío.
* El estado debe pertenecer a los valores permitidos.
* La etapa debe pertenecer a los valores permitidos.
* La fecha de aplicación debe conservarse correctamente.
* Los años de experiencia no podrán ser negativos.
* Los enlaces proporcionados (LinkedIn y CV) deberán ser válidos cuando existan.

---

## Estados de candidatura

### Descripción

El estado representa la situación general de una candidatura dentro del proceso de selección.

### Valores permitidos por la API

* `received`
* `in_progress`
* `selected`
* `discarded`

### Reglas de negocio

* Los valores de la API nunca deberán mostrarse directamente al usuario.
* La interfaz deberá utilizar siempre las siguientes etiquetas:

| Valor API   | Etiqueta     |
| ----------- | ------------ |
| received    | Recibida     |
| in_progress | En proceso   |
| selected    | Seleccionada |
| discarded   | Descartada   |

---

## Etapas del proceso

### Descripción

La etapa representa el punto del proceso de selección en el que se encuentra una candidatura.

### Valores permitidos por la API

* `pending`
* `review`
* `personal_interview`
* `technical_interview`
* `offer_presented`

### Reglas de negocio

* Los valores internos de la API nunca deberán mostrarse al usuario.
* La interfaz utilizará siempre las siguientes etiquetas:

| Valor API           | Etiqueta              |
| ------------------- | --------------------- |
| pending             | Pendiente de revisión |
| review              | En revisión           |
| personal_interview  | Entrevista personal   |
| technical_interview | Entrevista técnica    |
| offer_presented     | Oferta presentada     |

---

## Notas internas

### Descripción

Las notas permiten registrar información interna sobre cada candidato.

### Reglas de negocio

* Toda nota deberá estar asociada a un único candidato.
* Las notas únicamente serán visibles desde la página de detalle del candidato.
* Las notas podrán añadirse y eliminarse.
* La eliminación de una nota no deberá afectar al resto de información del candidato.

---

## Registro de candidaturas

### Reglas de negocio

* Antes de enviar una candidatura deberán validarse todos los campos obligatorios.
* No deberá enviarse información incompleta a la API.
* Tras un registro correcto, la interfaz deberá reflejar inmediatamente el nuevo candidato.
* Si el registro falla, el usuario deberá recibir un mensaje de error claro.

---

## Edición de candidaturas

### Reglas de negocio

* Solo podrán modificarse los datos permitidos por la API.
* Antes del envío deberán validarse nuevamente los datos.
* Tras una modificación correcta, la información visible deberá actualizarse sin recargar la página.

---

## Actualización de estado y etapa

### Reglas de negocio

* Estado y etapa podrán modificarse de forma independiente.
* Toda actualización deberá realizarse mediante la API.
* Tras una actualización correcta, la interfaz deberá mostrar inmediatamente el nuevo valor.
* Si la operación falla, deberá mostrarse un mensaje de error.

---

## Búsqueda y filtros

### Reglas de negocio

* La búsqueda deberá realizarse por nombre o correo electrónico.
* Los filtros deberán aplicarse sin recargar la página.
* Deberá ser posible combinar filtro por estado y filtro por etapa.
* Los filtros deberán conservarse durante la navegación siempre que sea posible mediante los parámetros de la URL.

---

## Comunicación con la API

### Reglas de negocio

Todas las operaciones deberán realizarse de forma asíncrona utilizando `async/await`.

Cada petición deberá gestionar correctamente tres estados:

* Cargando.
* Éxito.
* Error.

La aplicación nunca deberá fallar silenciosamente ni dejar al usuario sin información sobre el resultado de la operación.

---

## Navegación

### Reglas de negocio

* La navegación entre el listado y el detalle utilizará el sistema de rutas de Next.js.
* No deberán producirse recargas completas de la página.
* Al regresar desde el detalle deberá mantenerse el contexto del listado siempre que sea posible.

---

## Reglas generales

Toda la aplicación deberá cumplir las siguientes normas:

* Mantener la coherencia entre la información mostrada y los datos recibidos desde la API.
* No mostrar nunca los valores internos de la API al usuario.
* No modificar directamente los datos recibidos desde la API.
* Gestionar correctamente errores de red y respuestas inválidas.
* Mantener una interfaz consistente tras cualquier operación de creación, edición, actualización o eliminación.
* Utilizar componentes reutilizables siempre que sea posible.
* Mantener una experiencia de usuario clara mediante estados de carga, éxito y error.

---

## Objetivo final

Todas las reglas de negocio descritas en este documento deberán respetarse en cualquier implementación del Talent Pipeline Tracker para garantizar un proceso de selección consistente, una correcta gestión de las candidaturas y una experiencia fiable para el equipo de People & Talent de Brasaland.
