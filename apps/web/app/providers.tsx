"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { useState, type ReactNode } from "react";

import { ToastProvider } from "@/components/ui/toast";

export function Providers({ children }: { children: ReactNode }) {
  // One client per browser tab; created in state so a re-render does not drop the cache.
  const [queryClient] = useState(() => new QueryClient());

  return (
    <QueryClientProvider client={queryClient}>
      <NuqsAdapter>
        <ToastProvider>{children}</ToastProvider>
      </NuqsAdapter>
    </QueryClientProvider>
  );
}
