"use client";

import { RotateCw } from "lucide-react";

import { AppHeader } from "@/components/documents/AppHeader";
import { BackLink } from "@/components/documents/BackLink";
import { Button } from "@/components/ui/button";
import { errorTitles, texts } from "@/lib/texts";

/** A screen that failed to render: retry it or go back, instead of Next's blank error page. */
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <>
      <AppHeader />
      <main className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-8 lg:py-12">
        <BackLink className="-ml-3" />
        <h1 className="text-h2">{errorTitles.internal}</h1>
        <Button variant="secondary" icon={RotateCw} onClick={reset} className="self-start">
          {texts["common.retry"]}
        </Button>
      </main>
    </>
  );
}
