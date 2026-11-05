"use client";

import { useEffect, useState } from "react";

import { fetchIngredient } from "@/services/inventory";
import type { Ingredient } from "@/types/inventory";

interface IngredientStockResult {
  key: string;
  ingredient: Ingredient | null;
  error: string | null;
}

export function useInventoryIngredientStock(ingredientId: number | null) {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<IngredientStockResult | null>(null);
  const [requestLoading, setRequestLoading] = useState(false);
  const key = JSON.stringify([ingredientId, attempt]);
  const loading = ingredientId !== null
    && (requestLoading || result?.key !== key);

  useEffect(() => {
    const controller = new AbortController();
    if (ingredientId === null) return () => controller.abort();
    const requestedIngredientId = ingredientId;

    async function loadIngredient() {
      try {
        const ingredient = await fetchIngredient(requestedIngredientId, controller.signal);
        if (!controller.signal.aborted) {
          setResult({ key, ingredient, error: null });
        }
      } catch (error: unknown) {
        if (!controller.signal.aborted) {
          setResult({
            key,
            ingredient: null,
            error: error instanceof Error
              ? error.message
              : "No se pudo consultar el stock. Inténtalo de nuevo.",
          });
        }
      } finally {
        if (!controller.signal.aborted) setRequestLoading(false);
      }
    }

    void loadIngredient();
    return () => controller.abort();
  }, [ingredientId, key]);

  return {
    ingredient: ingredientId !== null && result?.key === key
      ? result.ingredient
      : null,
    loading,
    error: ingredientId !== null && result?.key === key ? result.error : null,
    refresh: () => setAttempt((value) => value + 1),
  };
}