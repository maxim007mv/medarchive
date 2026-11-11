"use client";

import { useEffect, useState } from "react";

import { cn } from "./cn";

/**
 * Placeholder block with the shimmer (brandbook §12). Size it with `className`; the container
 * that holds the skeleton carries the `role="status"` and its label.
 */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("skeleton-shimmer rounded-sm", className)} />;
}

/**
 * `true` only after `active` has stayed `true` for `delayMs`, so fast requests show no skeleton
 * at all (FE-07: «Загрузка списка < 1 с: ничего»).
 */
export function useDelayedFlag(active: boolean, delayMs = 1000): boolean {
  const [elapsed, setElapsed] = useState(false);

  useEffect(() => {
    if (!active) return;
    const timer = setTimeout(() => setElapsed(true), delayMs);
    return () => {
      clearTimeout(timer);
      setElapsed(false);
    };
  }, [active, delayMs]);

  return active && elapsed;
}
