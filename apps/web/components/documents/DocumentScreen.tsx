"use client";

import { ArrowLeft, Download, ExternalLink, Pencil, Trash2 } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { Alert } from "@/components/ui/alert";
import { Button, buttonClasses } from "@/components/ui/button";
import { TypeTag, UndatedTag } from "@/components/ui/tag";
import { isApiError } from "@/lib/api/errors";
import { browserTimeZone, type DocumentWithEtag, useDocument, useSession } from "@/lib/api/queries";
import { formatDate, formatDateTime, formatSize } from "@/lib/format";
import { errorTitles, t, texts } from "@/lib/texts";

import { AppHeader } from "./AppHeader";
import { LIST_URL_KEY } from "./ArchiveScreen";
import { NotePanel } from "./NotePanel";
import { OfflineBanner, useOfflineReason } from "./OfflineBanner";
import { contentUrl, PdfViewer } from "./PdfViewer";
import { RowMenu } from "./RowMenu";
import { useProblem } from "./use-problem";

// Loaded on first use: the form with its validation is not needed to read the document.
const EditPanel = dynamic(() => import("./EditPanel").then((module) => module.EditPanel));
const DeleteDialog = dynamic(() => import("./DeleteDialog").then((module) => module.DeleteDialog));

/** «Все документы» goes back to the list with the filters it was opened from (FE-16). */
function useBackHref(): string {
  const [href, setHref] = useState("/");
  useEffect(() => setHref(sessionStorage.getItem(LIST_URL_KEY) ?? "/"), []);
  return href;
}

function LinkButton({
  href,
  icon,
  children,
  newTab,
}: {
  href: string;
  icon: ReactNode;
  children: ReactNode;
  newTab?: boolean;
}) {
  return (
    <a
      href={href}
      {...(newTab ? { target: "_blank", rel: "noopener" } : { download: "" })}
      className={buttonClasses({ variant: "secondary", size: "sm" })}
    >
      <span className="inline-flex items-center gap-2">
        {icon}
        {children}
      </span>
    </a>
  );
}

/** `/documents/{id}`: D09, D10, M06. */
export function DocumentScreen({ id }: { id: string }) {
  const router = useRouter();
  const session = useSession();
  const document = useDocument(id);
  const backHref = useBackHref();
  const problem = useProblem(document.error);

  useEffect(() => {
    if (session.data === null) router.replace("/");
  }, [session.data, router]);

  return (
    <div className="flex min-h-dvh flex-col lg:h-dvh">
      <AppHeader showSettings />
      <OfflineBanner />
      {isApiError(document.error, "not_found") ? (
        <main className="mx-auto flex max-w-md flex-col items-center gap-4 px-4 py-16 text-center">
          <h1 className="text-h2">{errorTitles.not_found}</h1>
          <Link href={backHref} className={buttonClasses({ variant: "primary" })}>
            {texts["doc.notFound.back"]}
          </Link>
        </main>
      ) : document.data ? (
        <DocumentView
          current={document.data}
          timeZone={session.data?.timezone ?? browserTimeZone()}
          backHref={backHref}
          onDeleted={() => router.push(backHref)}
        />
      ) : (
        problem && (
          <main className="px-4 py-8">
            <Alert variant="danger" title={problem.title} />
          </main>
        )
      )}
    </div>
  );
}

function DocumentView({
  current,
  timeZone,
  backHref,
  onDeleted,
}: {
  current: DocumentWithEtag;
  timeZone: string;
  backHref: string;
  onDeleted: () => void;
}) {
  const { document } = current;
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const offlineReason = useOfflineReason();
  const pages = document.file.page_count ?? 1;

  return (
    <main className="flex flex-col lg:min-h-0 lg:flex-1 lg:flex-row">
      <div className="border-border flex min-h-0 flex-col lg:flex-1 lg:border-r">
        <div className="border-border flex h-12 items-center gap-2 border-b px-4">
          <Link href={backHref} className={buttonClasses({ variant: "tertiary", size: "sm" })}>
            <span className="inline-flex items-center gap-2">
              <ArrowLeft size={16} strokeWidth={1.75} aria-hidden />
              {texts["doc.back"]}
            </span>
          </Link>
          <div className="ml-auto lg:hidden">
            <RowMenu
              label={texts["doc.more"]}
              onDelete={() => setDeleting(true)}
              disabledReason={offlineReason}
            />
          </div>
        </div>
        <div className="h-96 p-4 lg:h-auto lg:flex-1 lg:p-6">
          <PdfViewer documentId={document.id} title={document.title} />
        </div>
      </div>

      <aside className="flex flex-col gap-6 p-4 lg:w-105 lg:overflow-y-auto lg:p-6">
        {editing ? (
          <EditPanel
            current={current}
            onDone={() => setEditing(false)}
            disabledReason={offlineReason}
          />
        ) : (
          <section className="flex flex-col gap-4">
            <h1 className="text-h2 break-words">{document.title}</h1>
            <div>
              <TypeTag type={document.type} />
            </div>
            <dl className="text-body grid grid-cols-2 gap-x-4 gap-y-3">
              <dt className="text-text2">{texts["doc.meta.documentDate"]}</dt>
              <dd className="text-mono font-mono">
                {document.document_date ? formatDate(document.document_date) : <UndatedTag />}
              </dd>
              <dt className="text-text2">{texts["doc.meta.uploadedAt"]}</dt>
              <dd className="text-mono font-mono">
                {formatDateTime(document.uploaded_at, timeZone)}
              </dd>
              <dt className="text-text2">{texts["doc.meta.file"]}</dt>
              <dd className="flex min-w-0 flex-col gap-0.5">
                <span className="break-all">{document.file.original_name}</span>
                <span className="text-caption text-text3">
                  {t("doc.meta.fileInfo", { size: formatSize(document.file.size_bytes), n: pages })}
                </span>
              </dd>
            </dl>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="secondary"
                size="sm"
                icon={Pencil}
                onClick={() => setEditing(true)}
                disabled={Boolean(offlineReason)}
                disabledReason={offlineReason}
              >
                {texts["doc.edit"]}
              </Button>
              <LinkButton
                href={contentUrl(document.id, "attachment")}
                icon={<Download size={16} strokeWidth={1.75} aria-hidden />}
              >
                {texts["doc.download"]}
              </LinkButton>
              <LinkButton
                href={contentUrl(document.id, "inline")}
                newTab
                icon={<ExternalLink size={16} strokeWidth={1.75} aria-hidden />}
              >
                {texts["doc.openTab"]}
              </LinkButton>
            </div>
          </section>
        )}

        <div className="border-border border-t pt-6">
          <NotePanel documentId={document.id} disabledReason={offlineReason} />
        </div>

        <div className="border-border mt-auto hidden border-t pt-4 lg:block">
          <Button
            variant="dangerText"
            size="sm"
            icon={Trash2}
            onClick={() => setDeleting(true)}
            disabled={Boolean(offlineReason)}
            disabledReason={offlineReason}
          >
            {texts["doc.delete"]}
          </Button>
        </div>
      </aside>

      {deleting && (
        <DeleteDialog
          target={document}
          getEtag={async () => current.etag}
          onClose={() => setDeleting(false)}
          onDeleted={onDeleted}
        />
      )}
    </main>
  );
}
