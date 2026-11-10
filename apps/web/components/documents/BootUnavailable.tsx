"use client";

import { RotateCw, WifiOff } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { texts } from "@/lib/texts";

/** Automatic retries of the first request: 5, 10, then every 30 s (04-customer-journey, stage 0). */
const RETRY_DELAYS_MS = [5000, 10_000, 30_000];

/** «Не удаётся открыть архив»: the session request did not reach the server. */
export function BootUnavailable({ onRetry, retrying }: { onRetry: () => void; retrying: boolean }) {
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (retrying) return;
    const delay = RETRY_DELAYS_MS[Math.min(attempt, RETRY_DELAYS_MS.length - 1)];
    const timer = setTimeout(() => {
      setAttempt((count) => count + 1);
      onRetry();
    }, delay);
    return () => clearTimeout(timer);
  }, [attempt, retrying, onRetry]);

  return (
    <main className="mx-auto flex max-w-md flex-col items-center gap-4 px-4 py-16 text-center">
      <WifiOff size={24} strokeWidth={1.75} className="text-text3" aria-hidden />
      <h1 className="text-h2">{texts["boot.unavailable.title"]}</h1>
      <p className="text-text2">{texts["boot.unavailable.text"]}</p>
      <Button variant="secondary" icon={RotateCw} loading={retrying} onClick={onRetry}>
        {texts["boot.unavailable.retry"]}
      </Button>
    </main>
  );
}
