import type { Metadata } from "next";

import { AppHeader } from "@/components/documents/AppHeader";
import { BackLink } from "@/components/documents/BackLink";
import { PolicyDocument } from "@/components/documents/PolicyDocument";
import { formatDate } from "@/lib/format";
import { policyMarkdown, policyVersion } from "@/lib/policy";
import { t, texts } from "@/lib/texts";

export const metadata: Metadata = { title: `${texts["policy.title"]} · ${texts["app.name"]}` };

/** The heading and the «Версия:» line of the file are replaced by the page's own (docs/texts.md §15). */
const body = policyMarkdown
  .split(/\n{2,}/)
  .slice(2)
  .join("\n\n");

export default function PolicyPage() {
  return (
    <>
      <AppHeader />
      <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-8 lg:py-12">
        <BackLink className="-ml-3" />
        <header className="flex flex-col gap-2">
          <h1 className="text-h1">{texts["policy.title"]}</h1>
          <p className="text-text3">{t("policy.version", { date: formatDate(policyVersion) })}</p>
        </header>
        <PolicyDocument markdown={body} />
      </main>
    </>
  );
}
