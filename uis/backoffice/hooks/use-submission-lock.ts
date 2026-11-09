"use client";

import { useRef, useState } from "react";

export function useSubmissionLock() {
  const submittingRef = useRef(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function run<T>(operation: () => Promise<T>): Promise<T | undefined> {
    if (submittingRef.current) return undefined;

    submittingRef.current = true;
    setIsSubmitting(true);

    try {
      return await operation();
    } finally {
      submittingRef.current = false;
      setIsSubmitting(false);
    }
  }

  return {
    isSubmitting,
    isLocked: () => submittingRef.current,
    run,
  };
}