import type { Metadata } from "next";

import { AppHeader } from "@/components/documents/AppHeader";
import { BackLink } from "@/components/documents/BackLink";
import { texts } from "@/lib/texts";

export const metadata: Metadata = { title: `${texts["notFound.title"]} · ${texts["app.name"]}` };

export default function NotFound() {
  return (
    <>
      <AppHeader />
      <main className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-8 lg:py-12">
        <BackLink className="-ml-3" />
        <h1 className="text-h1">{texts["notFound.title"]}</h1>
        <p className="text-text2">{texts["notFound.text"]}</p>
      </main>
    </>
  );
}
