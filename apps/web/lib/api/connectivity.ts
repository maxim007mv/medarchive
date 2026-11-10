import { useSyncExternalStore } from "react";

/**
 * Whether the API is reachable (FE-21, D14): `navigator.onLine` plus the outcome of the last request.
 * One failed request turns the banner on; any answer from the server turns it off.
 */
let lastRequestFailed = false;
const listeners = new Set<() => void>();

function notify(): void {
  for (const listener of listeners) listener();
}

export function reportRequestOutcome({ reachable }: { reachable: boolean }): void {
  if (lastRequestFailed === !reachable) return;
  lastRequestFailed = !reachable;
  notify();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener("online", listener);
  window.addEventListener("offline", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("online", listener);
    window.removeEventListener("offline", listener);
  };
}

function isOnline(): boolean {
  return navigator.onLine && !lastRequestFailed;
}

export function useIsOnline(): boolean {
  return useSyncExternalStore(subscribe, isOnline, () => true);
}
