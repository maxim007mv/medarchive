import type { Metadata } from "next";

import { AppHeader } from "@/components/documents/AppHeader";
import { RestoreForm } from "@/components/documents/RestoreForm";
import { texts } from "@/lib/texts";

export const metadata: Metadata = { title: `${texts["restore.title"]} · ${texts["app.name"]}` };

export default function RestorePage() {
  return (
    <>
      <AppHeader />
      <main className="mx-auto flex w-full max-w-lg flex-col gap-6 px-4 py-12">
        <h1 className="text-h1">{texts["restore.title"]}</h1>
        <p className="text-text2">{texts["accessKey.text"]}</p>
        <RestoreForm />
      </main>
    </>
  );
}
