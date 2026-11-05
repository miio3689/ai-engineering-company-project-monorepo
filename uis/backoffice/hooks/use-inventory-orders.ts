"use client";

import { useEffect, useState } from "react";

import { fetchIngredients, fetchOrders } from "@/services/inventory";
import type { IngredientUnit, InventoryOrder } from "@/types/inventory";

interface InventoryOrdersResult {
  key: string;
  orders: InventoryOrder[];
  unitsByIngredientId: Record<number, IngredientUnit>;
  error: string | null;
}

export function useInventoryOrders() {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<InventoryOrdersResult | null>(null);
  const [requestLoading, setRequestLoading] = useState(true);
  const key = String(attempt);
  const loading = requestLoading || result?.key !== key;

  useEffect(() => {
    const controller = new AbortController();

    async function loadInventoryOrders() {
      const [ordersResult, ingredientsResult] = await Promise.allSettled([
        fetchOrders(controller.signal),
        fetchIngredients(controller.signal),
      ]);

      if (controller.signal.aborted) return;

      const unitsByIngredientId: Record<number, IngredientUnit> = {};
      if (ingredientsResult.status === "fulfilled") {
        for (const ingredient of ingredientsResult.value) {
          unitsByIngredientId[ingredient.id] = ingredient.unit;
        }
      }

      setResult({
        key,
        orders: ordersResult.status === "fulfilled" ? ordersResult.value : [],
        unitsByIngredientId,
        error: ordersResult.status === "rejected"
          ? ordersResult.reason instanceof Error
            ? ordersResult.reason.message
            : "No se pudo cargar el historial de órdenes. Inténtalo de nuevo."
          : null,
      });
    }

    void loadInventoryOrders().finally(() => {
      if (!controller.signal.aborted) setRequestLoading(false);
    });
    return () => controller.abort();
  }, [key]);

  return {
    orders: result?.key === key ? result.orders : [],
    unitsByIngredientId: result?.key === key ? result.unitsByIngredientId : {},
    loading,
    error: result?.key === key ? result.error : null,
    retry: () => setAttempt((value) => value + 1),
  };
}