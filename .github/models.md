# Models

## Objetivo

Este documento define las entidades de negocio utilizadas en el proyecto de Brasaland.

Las interfaces describen la estructura de los datos con los que trabajará la aplicación. No contienen reglas de validación ni lógica de negocio; esas se documentan en otros archivos.

---

## Price

Representa un valor monetario en las dos monedas soportadas por la empresa.

```ts
interface Price {
  USD: number;
  COP: number;
}
```

---

## MenuItem

Representa un producto del menú de Brasaland.

```ts
interface MenuItem {
  id: string;
  name: string;
  category: MenuCategory;
  basePrice: Price;
  ingredientCost: Price;
  prepTimeMinutes: number;
  isAvailableInColombia: boolean;
  isAvailableInUSA: boolean;
  allergens: string[];
  status: MenuItemStatus;
}
```

### Propiedades

* **id:** Identificador único del producto.
* **name:** Nombre del producto.
* **category:** Categoría del menú.
* **basePrice:** Precio de venta.
* **ingredientCost:** Coste de ingredientes.
* **prepTimeMinutes:** Tiempo medio de preparación.
* **isAvailableInColombia:** Disponibilidad en Colombia.
* **isAvailableInUSA:** Disponibilidad en Estados Unidos.
* **allergens:** Lista de alérgenos.
* **status:** Estado del producto.

---

## SaleTransaction

Representa una venta realizada en una locación.

```ts
interface SaleTransaction {
  id: string;
  locationId: string;
  itemId: string;
  quantity: number;
  totalPrice: Price;
  paymentMethod: PaymentMethod;
  timestamp: Date;
  waiterName: string;
}
```

### Propiedades

* **id:** Identificador de la venta.
* **locationId:** Locación donde se realizó la venta.
* **itemId:** Producto vendido.
* **quantity:** Cantidad vendida.
* **totalPrice:** Importe total de la venta.
* **paymentMethod:** Método de pago.
* **timestamp:** Fecha y hora de la venta.
* **waiterName:** Empleado responsable de la venta.

---

## Location

Representa un restaurante de Brasaland.

```ts
interface Location {
  id: string;
  name: string;
  city: string;
  country: Country;
  openingYear: number;
  seatingCapacity: number;
  staffCount: number;
  monthlyRentCost: Price;
  averageMonthlyUtilities: Price;
  manager: string;
  status: LocationStatus;
}
```

### Propiedades

* **id:** Identificador de la locación.
* **name:** Nombre del restaurante.
* **city:** Ciudad.
* **country:** País.
* **openingYear:** Año de apertura.
* **seatingCapacity:** Capacidad máxima de clientes.
* **staffCount:** Número de empleados.
* **monthlyRentCost:** Coste mensual del alquiler.
* **averageMonthlyUtilities:** Coste medio mensual de suministros.
* **manager:** Responsable de la locación.
* **status:** Estado operativo.

---

## WasteRecord

Representa un registro de desperdicio de alimentos.

```ts
interface WasteRecord {
  id: string;
  locationId: string;
  itemId: string;
  quantity: number;
  reason: WasteReason;
  cost: Price;
  timestamp: Date;
  reportedBy: string;
}
```

### Propiedades

* **id:** Identificador del registro.
* **locationId:** Locación donde ocurrió el desperdicio.
* **itemId:** Producto afectado.
* **quantity:** Cantidad desperdiciada.
* **reason:** Motivo del desperdicio.
* **cost:** Coste económico del desperdicio.
* **timestamp:** Fecha y hora del registro.
* **reportedBy:** Empleado que registró el desperdicio.

---

## CountryMetrics

Representa las métricas agregadas de cada país.

```ts
interface CountryMetrics {
  totalLocations: number;
  totalRevenue: Price;
  averageRevenuePerLocation: Price;
  totalSales: number;
}
```

### Propiedades

* **totalLocations:** Número de restaurantes del país.
* **totalRevenue:** Ingresos totales.
* **averageRevenuePerLocation:** Ingreso medio por restaurante.
* **totalSales:** Número total de ventas.

---

## Tipos y enumeraciones

### MenuCategory

```ts
type MenuCategory =
  | "Meat"
  | "Side"
  | "Beverage"
  | "Dessert"
  | "Combo";
```

### MenuItemStatus

```ts
type MenuItemStatus =
  | "Active"
  | "Seasonal"
  | "Discontinued";
```

### PaymentMethod

```ts
type PaymentMethod =
  | "Cash"
  | "Credit card"
  | "Debit card"
  | "Digital wallet";
```

### Country

```ts
type Country =
  | "Colombia"
  | "USA";
```

### LocationStatus

```ts
type LocationStatus =
  | "Active"
  | "Temporarily closed"
  | "Under renovation";
```

### WasteReason

```ts
type WasteReason =
  | "Expired"
  | "Cooking error"
  | "Customer return"
  | "Damage"
  | "Other";
```

---

## Relaciones entre entidades

Las entidades se relacionan mediante identificadores (`id`), evitando dependencias directas entre objetos.

* Un **Location** puede tener múltiples **SaleTransaction**.
* Un **Location** puede tener múltiples **WasteRecord**.
* Un **MenuItem** puede aparecer en múltiples **SaleTransaction**.
* Un **MenuItem** puede aparecer en múltiples **WasteRecord**.

Las relaciones se realizan mediante los campos `locationId` e `itemId`, lo que facilita las operaciones de búsqueda, filtrado y agregación de datos.
