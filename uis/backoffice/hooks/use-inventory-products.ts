"use client";

import { useEffect, useState } from "react";

import { fetchIngredients } from "@/services/inventory";
import type { Ingredient } from "@/types/inventory";

interface IngredientListResult {
  attempt: number;
  ingredients: Ingredient[];
  error: string | null;
}

export function useInventoryProducts() {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<IngredientListResult | null>(null);
  const [requestLoading, setRequestLoading] = useState(true);
  const loading = requestLoading || result?.attempt !== attempt;

  useEffect(() => {
    const controller = new AbortController();

    async function loadIngredients() {
      try {
        const ingredients = await fetchIngredients(controller.signal);
        if (!controller.signal.aborted) {
          setResult({ attempt, ingredients, error: null });
        }
      } catch (error: unknown) {
        if (!controller.signal.aborted) {
          setResult({
            attempt,
            ingredients: [],
            error: error instanceof Error
              ? error.message
              : "No se pudo cargar el inventario. Inténtalo de nuevo.",
          });
        }
      } finally {
        if (!controller.signal.aborted) setRequestLoading(false);
      }
    }

    void loadIngredients();
    return () => controller.abort();
  }, [attempt]);

  return {
    ingredients: result?.attempt === attempt ? result.ingredients : [],
    loading,
    error: result?.attempt === attempt ? result.error : null,
    retry: () => setAttempt((value) => value + 1),
  };
}