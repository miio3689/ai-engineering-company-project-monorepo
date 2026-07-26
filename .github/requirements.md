# Requirements

## Objetivo

Este documento define los requisitos funcionales que debe cumplir la implementación del proyecto.

Todas las funciones deberán desarrollarse en **TypeScript**, utilizar tipado estricto y respetar la estructura del proyecto.

---

## Collections

**Archivo:**

```text
src/utils/collections.ts
```

### filterSalesByLocation()

```ts
filterSalesByLocation(
  sales: SaleTransaction[],
  locationId: string
): SaleTransaction[]
```

#### Requisitos

* Retornar únicamente las ventas pertenecientes a la locación indicada.
* No modificar el array original.

---

### filterSalesByDateRange()

```ts
filterSalesByDateRange(
  sales: SaleTransaction[],
  startDate: Date,
  endDate: Date
): SaleTransaction[]
```

#### Requisitos

* Retornar las ventas comprendidas entre ambas fechas.
* La fecha inicial y final son inclusivas.
* No modificar el array original.

---

### filterMenuItemsByCategory()

```ts
filterMenuItemsByCategory(
  items: MenuItem[],
  category: MenuCategory
): MenuItem[]
```

#### Requisitos

* Retornar únicamente los productos pertenecientes a la categoría indicada.
* No modificar el array original.

---

### filterActiveLocations()

```ts
filterActiveLocations(
  locations: Location[]
): Location[]
```

#### Requisitos

* Retornar únicamente las locaciones con estado **Active**.
* No modificar el array original.

---

### sortLocationsByCapacity()

```ts
sortLocationsByCapacity(
  locations: Location[],
  order: "asc" | "desc"
): Location[]
```

#### Requisitos

* Ordenar por capacidad de asientos.
* Permitir orden ascendente y descendente.
* No modificar el array original.

---

### sortMenuItemsByPrice()

```ts
sortMenuItemsByPrice(
  items: MenuItem[],
  currency: "USD" | "COP",
  order: "asc" | "desc"
): MenuItem[]
```

#### Requisitos

* Ordenar por precio.
* Permitir seleccionar la moneda.
* Permitir orden ascendente y descendente.
* No modificar el array original.

---

## Search

**Archivo:**

```text
src/utils/search.ts
```

### findLocationById()

#### Requisitos

* Implementar una búsqueda lineal.
* Buscar mediante el identificador.
* Retornar la locación encontrada.
* Retornar `null` cuando no exista.

---

### findMenuItemByName()

#### Requisitos

* Implementar una búsqueda lineal.
* Comparar los nombres sin distinguir mayúsculas y minúsculas.
* Retornar el elemento encontrado.
* Retornar `null` cuando no exista.

---

### binarySearchLocationByCapacity()

#### Requisitos

* Implementar una búsqueda binaria.
* Asumir que el array recibido ya está ordenado por capacidad.
* Retornar el índice del elemento encontrado.
* Retornar `-1` cuando no exista.

---

## Transformations

**Archivo:**

```text
src/utils/transformations.ts
```

### Cálculos financieros

Funciones a implementar:

* `calculateDailyRevenue()`
* `calculateLocationMargin()`
* `calculateWasteCost()`
* `convertCurrency()`

#### Requisitos

* Trabajar correctamente con USD y COP.
* Redondear todos los resultados a dos decimales.
* Utilizar una tasa fija de conversión:

```text
1 USD = 4000 COP
```

* Si la moneda de origen y destino son iguales, devolver la cantidad original.

---

### Scoring de rendimiento

Funciones a implementar:

* `scoreLocationPerformance()`
* `rankLocationsByPerformance()`

#### Requisitos

El cálculo del rendimiento debe tener en cuenta:

* Ingresos diarios.
* Utilización de la capacidad del restaurante.
* Control del desperdicio.
* Margen de beneficio.

La puntuación final debe estar comprendida entre **0 y 100**.

---

### Reportes y agregaciones

Funciones a implementar:

* `countSalesByPaymentMethod()`
* `calculateAverageTicket()`
* `findTopSellingItems()`
* `groupWasteByReason()`
* `calculateCountryComparison()`

#### Requisitos

* Generar información agregada.
* No modificar las colecciones originales.
* Mantener el tipado de todos los resultados.

---

## Validations

**Archivo:**

```text
src/utils/validations.ts
```

### validateMenuItem()

#### Requisitos

Validar todas las reglas de negocio correspondientes a un producto del menú.

Debe devolver:

```ts
{
  valid: boolean;
  errors: string[];
}
```

---

### validateSaleTransaction()

#### Requisitos

Validar todas las reglas de negocio correspondientes a una venta.

Debe devolver:

```ts
{
  valid: boolean;
  errors: string[];
}
```

---

### validateLocation()

#### Requisitos

Validar todas las reglas de negocio correspondientes a una locación.

Debe devolver:

```ts
{
  valid: boolean;
  errors: string[];
}
```

---

## Requisitos generales

Todas las funciones del proyecto deberán cumplir los siguientes principios:

* Utilizar TypeScript con tipado estricto.
* No utilizar `any`.
* Tener una única responsabilidad.
* Ser reutilizables.
* Utilizar nombres descriptivos.
* Manejar correctamente arrays vacíos.
* Manejar correctamente datos inválidos.
* No modificar los parámetros recibidos, salvo que se indique expresamente.
* Devolver siempre el tipo especificado.
* Mantener un comportamiento determinista.

---

## Calidad del código

La implementación deberá:

* Compilar sin errores de TypeScript.
* Seguir la estructura del proyecto.
* Mantener una separación clara de responsabilidades.
* Priorizar la legibilidad del código.
* Evitar duplicación de lógica.
* Utilizar métodos funcionales (`map`, `filter`, `reduce`, `find`, `some`, `every`, etc.) cuando mejoren la claridad y el mantenimiento del código.

---

## Resultado esperado

Al finalizar el proyecto deberá existir una biblioteca de utilidades TypeScript robusta, reutilizable y correctamente tipada que permita gestionar, transformar, validar y analizar la información operativa de Brasaland y sirva como base para futuros desarrollos del sistema.
