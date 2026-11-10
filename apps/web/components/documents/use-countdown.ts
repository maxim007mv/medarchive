import { useEffect, useState } from "react";

/**
 * Seconds left of a `Retry-After` (FE-21), `null` when there is nothing to wait for. Restarts when
 * `source` (the error that carried the header) changes. Counts timer ticks rather than reading the
 * clock, so a frozen `Date` in tests does not stop it.
 */
export function useCountdown(seconds: number | null, source: unknown): number | null {
  const [left, setLeft] = useState(seconds);

  useEffect(() => {
    setLeft(seconds);
    if (seconds === null) return;
    const timer = setInterval(() => {
      setLeft((previous) => (previous !== null && previous > 1 ? previous - 1 : null));
    }, 1000);
    return () => clearInterval(timer);
  }, [seconds, source]);

  return left;
}
