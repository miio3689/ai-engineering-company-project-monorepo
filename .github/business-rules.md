# Business Rules

## Objetivo

Este documento define las reglas de negocio que deben cumplirse durante el procesamiento de la información de Brasaland.

Estas reglas son independientes de la implementación y representan las restricciones funcionales del dominio. Todas las validaciones deberán respetarlas.

---

## MenuItem

### Descripción

Un **MenuItem** representa un producto disponible en el menú de Brasaland.

### Reglas de negocio

* El nombre del producto no puede estar vacío.
* El precio en USD debe ser mayor que cero.
* El precio en COP debe ser mayor que cero.
* El coste de ingredientes en USD debe ser mayor que cero.
* El coste de ingredientes en COP debe ser mayor que cero.
* El tiempo de preparación debe ser mayor que 0 minutos.
* El tiempo de preparación no puede superar los 60 minutos.
* El producto debe estar disponible al menos en uno de los dos países.
* El estado del producto debe pertenecer a los valores permitidos.

---

## SaleTransaction

### Descripción

Una **SaleTransaction** representa una venta realizada en un restaurante.

### Reglas de negocio

* La cantidad vendida debe ser mayor que cero.
* El importe total en USD debe ser mayor que cero.
* El importe total en COP debe ser mayor que cero.
* El nombre del empleado que realizó la venta no puede estar vacío.
* Toda venta debe estar asociada a una locación existente.
* Toda venta debe estar asociada a un producto existente.

---

## Location

### Descripción

Una **Location** representa un restaurante de Brasaland.

### Reglas de negocio

* El año de apertura debe ser igual o posterior a 2008.
* El año de apertura no puede ser posterior al año actual.
* La capacidad del restaurante debe ser mayor que cero.
* El número de empleados debe ser mayor que cero.
* El coste mensual del alquiler debe ser mayor que cero en ambas monedas.
* El coste medio mensual de suministros debe ser mayor que cero en ambas monedas.
* El nombre del gerente no puede estar vacío.
* El estado de la locación debe pertenecer a los valores permitidos.

---

## WasteRecord

### Descripción

Un **WasteRecord** representa un registro de desperdicio de alimentos.

### Reglas de negocio

* La cantidad desperdiciada debe ser mayor que cero.
* El coste del desperdicio debe ser mayor que cero en ambas monedas.
* El empleado que registra el desperdicio no puede estar vacío.
* Toda incidencia debe estar asociada a una locación existente.
* Toda incidencia debe estar asociada a un producto existente.
* El motivo del desperdicio debe pertenecer a los valores permitidos.

---

## Conversión de moneda

### Tasa de cambio

Todas las conversiones deberán utilizar una tasa fija.

```text
1 USD = 4000 COP
```

### Reglas

* Si la moneda de origen y destino son iguales, no debe realizarse ninguna conversión.
* Todos los resultados deberán redondearse a dos decimales.

---

## Cálculo del margen

### Fórmula

El margen de beneficio de una locación se calcula mediante la siguiente expresión:

```text
((Ingreso Total - Coste Total de Ingredientes) / Ingreso Total) × 100
```

### Reglas

* Solo deben utilizarse las ventas pertenecientes a la locación evaluada.
* El coste de ingredientes debe obtenerse a partir del `MenuItem` correspondiente.
* El resultado se expresará como un porcentaje.
* El resultado se redondeará a dos decimales.

---

## Cálculo del rendimiento de una locación

### Puntuación máxima

La puntuación total será un valor comprendido entre **0 y 100**.

### Distribución

#### Rendimiento económico

* Máximo: **40 puntos**.

Se calcula utilizando el ingreso medio diario de la locación.

---

#### Eficiencia

* Máximo: **30 puntos**.

Se calcula utilizando la relación entre el número de ventas y la capacidad del restaurante.

---

#### Control del desperdicio

* Máximo: **20 puntos**.

Cuanto menor sea el porcentaje de desperdicio respecto a los ingresos, mayor será la puntuación obtenida.

La puntuación mínima será **0**.

---

#### Margen de beneficio

* Máximo: **10 puntos**.

Se obtiene a partir del margen calculado para la locación.

---

## Reportes

### Conteo por método de pago

Los reportes deberán indicar el número de ventas realizadas mediante cada método de pago.

---

### Ticket medio

El ticket medio deberá calcularse utilizando la moneda seleccionada.

El resultado se redondeará a dos decimales.

---

### Productos más vendidos

Los productos deberán ordenarse de mayor a menor según la cantidad total vendida.

---

### Agrupación de desperdicios

Los registros deberán agruparse según el motivo del desperdicio.

---

### Comparativa por país

Las métricas deberán calcularse de forma independiente para:

* Colombia
* USA

Cada país deberá incluir:

* Número total de locaciones.
* Ingresos totales.
* Ingreso medio por locación.
* Número total de ventas.

---

## Reglas generales

Todas las funciones del proyecto deberán cumplir las siguientes normas:

* No modificar los datos recibidos por parámetro, salvo que se indique expresamente.
* Trabajar correctamente con colecciones vacías.
* Manejar correctamente datos inválidos.
* Devolver siempre el tipo especificado.
* Mantener un comportamiento determinista.
* Utilizar funciones puras siempre que sea posible.
* Mantener la coherencia entre USD y COP en todos los cálculos financieros.

---

## Objetivo final

Todas las reglas de negocio descritas en este documento deberán respetarse en cualquier implementación del proyecto para garantizar la consistencia, la fiabilidad de los datos y la correcta operación de los sistemas internos de Brasaland.
