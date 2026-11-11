"use client";

import { useQueryClient } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { useDelayedFlag } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import {
  browserTimeZone,
  type DocumentItem,
  fetchDocumentEtag,
  queryKeys,
  type Session,
  useDocuments,
} from "@/lib/api/queries";
import { hasAppliedFilters, serializeFilters } from "@/lib/filters";
import { t, texts } from "@/lib/texts";

// Not lazy: it replaces the upload dialog in the same frame, a chunk still loading would leave
// the list without a scrim in between.
import { AccessKeyDialog } from "./AccessKeyDialog";
import { AppHeader } from "./AppHeader";
import { AppliedFilters } from "./AppliedFilters";
import type { DeleteTarget } from "./DeleteDialog";
import { DocumentCards } from "./DocumentCard";
import { DocumentTable, documentHref } from "./DocumentTable";
import { EmptyArchive } from "./EmptyArchive";
import { EmptySearch } from "./EmptySearch";
import { ListSkeleton } from "./ListSkeleton";
import { listSubtitle, undatedHint } from "./list-texts";
import { LIST_URL_KEY } from "./list-url";
import { OfflineBanner, useOfflineReason } from "./OfflineBanner";
import { Toolbar } from "./Toolbar";
import { useListFilters } from "./use-list-filters";

// Dialogs load on first use: the form, its validation and the export are not needed to show the list.
const UploadDialog = dynamic(() => import("./UploadDialog").then((module) => module.UploadDialog));
const ExportDialog = dynamic(() => import("./ExportDialog").then((module) => module.ExportDialog));
const DeleteDialog = dynamic(() => import("./DeleteDialog").then((module) => module.DeleteDialog));

/** `--dur-highlight` of tokens.json: how long a new row stays lit. */
const HIGHLIGHT_MS = 1200;

type SavedDocument = Pick<DocumentItem, "id" | "title">;
type Props = {
  session: Session;
  /** Files chosen on onboarding, before the archive existed. */
  initialFiles: File[];
  /** Their dialog has closed: the owner lets the files go. */
  onInitialFilesDone: () => void;
  /** Key of an archive created just now; shown once, after the first upload dialog closes. */
  issuedKey: string | null;
  onKeyShown: () => void;
};

/** D06..D08, D13, D14, M02..M05: the archive list with search, filters and dialogs. */
export function ArchiveScreen({
  session,
  initialFiles,
  onInitialFilesDone,
  issuedKey,
  onKeyShown,
}: Props) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const showToast = useToast();
  const offlineReason = useOfflineReason();
  const { filters, setFilters, resetAll, removeDates } = useListFilters();
  const documents = useDocuments(filters, { enabled: true });
  const showSkeleton = useDelayedFlag(documents.isPending);
  const timeZone = session.timezone ?? browserTimeZone();

  const [uploadFiles, setUploadFiles] = useState<File[] | null>(
    initialFiles.length > 0 ? initialFiles : null,
  );
  const [keyToShow, setKeyToShow] = useState<string | null>(null);
  const [exportOpen, setExportOpen] = useState(false);
  // ExportDialog is a dynamic chunk: by the time it mounts, activeElement is no longer «Экспорт».
  const exportOpenerRef = useRef<HTMLElement | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{
    item: DocumentItem;
    opener: HTMLElement | null;
  } | null>(null);
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const [highlightId, setHighlightId] = useState<string | null>(null);
  // Saved before the new archive's key is shown: the toast would cover the key dialog (and lead
  // away from it) and the row would light up unseen behind it, so both wait for «Готово».
  const [savedBeforeKey, setSavedBeforeKey] = useState<SavedDocument | null>(null);
  // The onboarding opener is gone by the time the key dialog closes; focus lands on the list.
  const headingRef = useRef<HTMLHeadingElement>(null);
  // Stable between renders: ExportDialog asks the server for a new composition when it changes.
  const selectedIds = useMemo(() => [...selected], [selected]);

  useEffect(() => {
    if (initialFiles.length > 0) setUploadFiles(initialFiles);
  }, [initialFiles]);

  useEffect(() => {
    sessionStorage.setItem(LIST_URL_KEY, serializeFilters("/", filters));
  }, [filters]);

  useEffect(() => {
    if (highlightId === null) return;
    const timer = setTimeout(() => setHighlightId(null), HIGHLIGHT_MS);
    return () => clearTimeout(timer);
  }, [highlightId]);

  const pages = documents.data?.pages ?? [];
  const items = pages.flatMap((page) => page.items);
  const first = pages[0];
  const total = first?.total ?? 0;
  const matched = first?.matched ?? 0;
  const filtered = hasAppliedFilters(filters);
  const archiveEmpty = documents.isSuccess && total === 0;
  const addFiles = (files: File[]) => files.length > 0 && setUploadFiles(files);

  function announceSaved(saved: SavedDocument) {
    setHighlightId(saved.id);
    showToast({
      title: t("upload.toast.added", { title: saved.title }),
      action: {
        label: texts["upload.toast.open"],
        onClick: () => router.push(documentHref(saved.id)),
      },
    });
  }

  function closeUpload() {
    setUploadFiles(null);
    if (initialFiles.length > 0) onInitialFilesDone();
    if (issuedKey) {
      setKeyToShow(issuedKey);
      onKeyShown();
    }
  }

  const toggle = useCallback((id: string, checked: boolean) => {
    setSelected((current) => {
      const next = new Set(current);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }, []);
  const askToDelete = useCallback(
    (item: DocumentItem, opener: HTMLElement | null) => setDeleteTarget({ item, opener }),
    [],
  );

  function drop(event: DragEvent) {
    event.preventDefault();
    if (!offlineReason) addFiles([...event.dataTransfer.files]);
  }

  const exportDisabledReason =
    offlineReason ?? (archiveEmpty ? texts["export.emptyArchive"] : undefined);
  const listProps = {
    items,
    timeZone,
    selected,
    onToggle: toggle,
    onDelete: askToDelete,
    highlightId,
    deleteDisabledReason: offlineReason,
  };

  return (
    <>
      <AppHeader
        showSettings
        actions={{
          onExport: (opener) => {
            exportOpenerRef.current = opener;
            setExportOpen(true);
          },
          onAdd: () => setUploadFiles([]),
          exportDisabledReason,
          addDisabledReason: offlineReason,
        }}
      />
      <OfflineBanner />

      {archiveEmpty ? (
        <EmptyArchive
          needsConsent={false}
          busy={false}
          onFiles={addFiles}
          disabledReason={offlineReason}
        />
      ) : (
        <main
          onDragOver={(event) => event.preventDefault()}
          onDrop={drop}
          className="mx-auto flex w-full max-w-screen-2xl flex-col gap-6 px-4 pt-6 pb-8 lg:px-6 lg:pt-8"
        >
          <div className="flex flex-col gap-1">
            <h1 ref={headingRef} tabIndex={-1} className="text-h1">
              {texts["list.title"]}
            </h1>
            {first && (
              <p className="text-caption text-text2">{listSubtitle(filters, first, filtered)}</p>
            )}
          </div>
          <Toolbar filters={filters} setFilters={setFilters} />
          {first && (
            <AppliedFilters
              filters={filters}
              matched={matched}
              total={total}
              onChange={(patch) => void setFilters(patch)}
              onResetAll={() => void resetAll()}
            />
          )}

          {showSkeleton && <ListSkeleton />}
          {items.length > 0 && (
            <>
              <div className="hidden lg:block">
                <DocumentTable
                  {...listProps}
                  orderBy={filters.order_by}
                  onOrderChange={(order_by) => void setFilters({ order_by })}
                />
              </div>
              <div className="lg:hidden">
                <DocumentCards {...listProps} />
              </div>
            </>
          )}
          {documents.isSuccess && !documents.isPlaceholderData && items.length === 0 && (
            <EmptySearch
              filters={filters}
              onResetSearch={() => void setFilters({ q: "" })}
              onRemoveDates={() => void removeDates()}
              onResetAll={() => void resetAll()}
            />
          )}
          {first && first.undated_excluded > 0 && (
            <UndatedHint
              count={first.undated_excluded}
              onShow={() => void setFilters({ undated: true })}
            />
          )}
          {/* Room for the pinned «Добавить PDF» bar on phones. */}
          <div aria-hidden className="h-24 md:hidden" />
        </main>
      )}

      {uploadFiles && (
        <UploadDialog
          initialFiles={uploadFiles}
          onClose={closeUpload}
          onSaved={(saved) => {
            void queryClient.invalidateQueries({ queryKey: queryKeys.allDocuments });
            if (issuedKey) setSavedBeforeKey(saved.document);
            else announceSaved(saved.document);
          }}
        />
      )}
      {keyToShow && (
        <AccessKeyDialog
          accessKey={keyToShow}
          finalFocus={headingRef}
          onClose={() => {
            setKeyToShow(null);
            if (savedBeforeKey) announceSaved(savedBeforeKey);
            setSavedBeforeKey(null);
          }}
        />
      )}
      {exportOpen && (
        <ExportDialog
          filters={filters}
          filtered={filtered}
          total={total}
          matched={matched}
          selectedIds={selectedIds}
          finalFocus={exportOpenerRef}
          onClose={() => setExportOpen(false)}
        />
      )}
      {deleteTarget && (
        <DeleteDialog
          target={deleteTarget.item satisfies DeleteTarget}
          getEtag={() => fetchDocumentEtag(deleteTarget.item.id)}
          returnFocusTo={deleteTarget.opener}
          onClose={() => setDeleteTarget(null)}
          onDeleted={() => {
            toggle(deleteTarget.item.id, false);
            setDeleteTarget(null);
          }}
        />
      )}
    </>
  );
}

function UndatedHint({ count, onShow }: { count: number; onShow: () => void }) {
  const { text, action } = undatedHint(count);
  return (
    <Alert variant="info">
      {text}{" "}
      <button
        type="button"
        onClick={onShow}
        className="text-text rounded-xs font-semibold underline"
      >
        {action}
      </button>
    </Alert>
  );
}
