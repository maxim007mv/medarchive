"use client";

import { ExternalLink, FileText } from "lucide-react";
import { useSyncExternalStore } from "react";

import { buttonClasses } from "@/components/ui/button";
import { t, texts } from "@/lib/texts";

export function contentUrl(documentId: string, disposition: "inline" | "attachment"): string {
  return `/api/v1/documents/${documentId}/content?disposition=${disposition}`;
}

const subscribeNever = () => () => undefined;
// Older engines lack the flag; only an explicit `false` means the browser cannot show PDF inline.
const canShowPdf = () => navigator.pdfViewerEnabled !== false;

/** Built-in browser viewer (FE-16, D09); a card with «В новой вкладке» where there is none. */
export function PdfViewer({ documentId, title }: { documentId: string; title: string }) {
  const inline = useSyncExternalStore(subscribeNever, canShowPdf, () => true);
  const inlineUrl = contentUrl(documentId, "inline");

  if (!inline) {
    return (
      <div className="bg-sunken flex h-full flex-col items-center justify-center gap-4 rounded-xl p-8 text-center">
        <FileText size={24} strokeWidth={1.75} className="text-text3" aria-hidden />
        <p className="text-body-l">{texts["doc.viewer.unsupported"]}</p>
        <a
          href={inlineUrl}
          target="_blank"
          rel="noopener"
          className={buttonClasses({ variant: "secondary" })}
        >
          <span className="inline-flex items-center gap-2">
            <ExternalLink size={20} strokeWidth={1.75} aria-hidden />
            {texts["doc.openTab"]}
          </span>
        </a>
      </div>
    );
  }

  return (
    <iframe
      src={`${inlineUrl}#view=FitH`}
      title={t("doc.viewer.title", { title })}
      className="bg-sunken h-full min-h-96 w-full border-0"
    />
  );
}
