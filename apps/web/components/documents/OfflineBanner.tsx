"use client";

import { useQueryClient } from "@tanstack/react-query";
import { RotateCw, WifiOff } from "lucide-react";

import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { useIsOnline } from "@/lib/api/connectivity";
import { texts } from "@/lib/texts";

/** D14: one banner instead of an error per action; the cached list stays on screen (FE-21). */
export function OfflineBanner() {
  const online = useIsOnline();
  const queryClient = useQueryClient();
  if (online) return null;

  return (
    <Banner
      icon={WifiOff}
      title={texts["offline.banner.title"]}
      action={
        <Button
          variant="secondary"
          size="sm"
          icon={RotateCw}
          onClick={() => void queryClient.refetchQueries({ type: "active" })}
        >
          {texts["offline.banner.retry"]}
        </Button>
      }
    >
      {texts["offline.banner.text"]}
    </Banner>
  );
}

/** Reason on every mutating button while the server is unreachable, `undefined` when online. */
export function useOfflineReason(): string | undefined {
  return useIsOnline() ? undefined : texts["offline.disabledReason"];
}
