"use client";

import * as RadixToast from "@radix-ui/react-toast";
import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import { texts } from "@/lib/texts";

export type ToastOptions = {
  title: string;
  action?: { label: string; onClick: () => void };
  /** 4 s by default; «Заметка очищена · Вернуть» stays 6 s. */
  durationMs?: number;
};

type ShownToast = ToastOptions & { id: number };

const DEFAULT_DURATION_MS = 4000;

const ShowToastContext = createContext<((toast: ToastOptions) => void) | null>(null);

const subscribeToNothing = () => () => undefined;

/** Toasts at the bottom centre, announced politely (FE-07, brandbook §10). */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ShownToast[]>([]);
  const nextId = useRef(0);
  // The viewport is rendered after hydration: Radix server-renders it with a style attribute,
  // which CSP style-src 'self' blocks, and a toast can only appear on the client anyway.
  const isClient = useSyncExternalStore(
    subscribeToNothing,
    () => true,
    () => false,
  );

  const show = useCallback((toast: ToastOptions) => {
    nextId.current += 1;
    setToasts((shown) => [...shown, { ...toast, id: nextId.current }]);
  }, []);

  const dismiss = (id: number) => setToasts((shown) => shown.filter((toast) => toast.id !== id));

  return (
    // Radix needs a non-empty label for the region and the announcement prefix; its defaults are English.
    <RadixToast.Provider
      duration={DEFAULT_DURATION_MS}
      swipeDirection="down"
      label={texts["toast.region"]}
    >
      <ShowToastContext value={show}>{children}</ShowToastContext>
      {toasts.map((toast) => (
        <RadixToast.Root
          key={toast.id}
          // "background" announces with aria-live="polite"; "foreground" would interrupt.
          type="background"
          duration={toast.durationMs}
          onOpenChange={(open) => !open && dismiss(toast.id)}
          className="bg-primary motion-safe:animate-dialog-in text-body text-on-primary shadow-3 flex max-w-full items-center gap-4 rounded-lg py-3 pr-3 pl-4"
        >
          <RadixToast.Title className="min-w-0">{toast.title}</RadixToast.Title>
          {toast.action && (
            <RadixToast.Action
              altText={toast.action.label}
              onClick={toast.action.onClick}
              className="bg-on-primary/15 text-on-primary duration-fast hover:bg-on-primary/25 shrink-0 rounded-md px-2.5 py-1.5 font-semibold transition-colors"
            >
              {toast.action.label}
            </RadixToast.Action>
          )}
        </RadixToast.Root>
      ))}
      {isClient && (
        <RadixToast.Viewport
          label={texts["toast.region"]}
          className="pb-safe fixed inset-x-0 bottom-0 z-50 flex flex-col items-center gap-2 px-4 outline-hidden md:pb-8"
        />
      )}
    </RadixToast.Provider>
  );
}

/** `show({ title, action })`; needs ToastProvider (app/providers.tsx). */
export function useToast(): (toast: ToastOptions) => void {
  const show = useContext(ShowToastContext);
  if (!show) throw new Error("useToast is used outside ToastProvider");
  return show;
}
