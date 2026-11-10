"use client";

import { Archive, Download } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button, buttonClasses } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { RadioRow, RadioRowGroup } from "@/components/ui/radio-row";
import { newIdempotencyKey } from "@/lib/api/client";
import { type ExportCreate, useCreateExport } from "@/lib/api/queries";
import { type DocumentFilters, toExportFilter } from "@/lib/filters";
import { formatSize, plural } from "@/lib/format";
import { plurals, t, texts } from "@/lib/texts";

export type ExportScope = ExportCreate["scope"];

/** «Только найденные» when the list is filtered, otherwise «Весь архив» (FE-20). */
export function defaultExportScope(filtered: boolean): ExportScope {
  return filtered ? "filtered" : "all";
}

type Props = {
  filters: DocumentFilters;
  filtered: boolean;
  total: number;
  matched: number;
  selectedIds: string[];
  onClose: () => void;
};

/**
 * D12 / M08. Each choice asks `POST /api/v1/exports` for its composition, so the button shows the
 * real size from `total_bytes`; the ZIP itself streams from `content_url`.
 */
export function ExportDialog({ filters, filtered, total, matched, selectedIds, onClose }: Props) {
  const [scope, setScope] = useState<ExportScope>(defaultExportScope(filtered));
  const createExport = useCreateExport();
  const { mutate, reset } = createExport;

  // One key per composition the person looks at; a retry of the same choice reuses it.
  const { body, idempotencyKey } = useMemo(() => {
    const idempotencyKey = newIdempotencyKey();
    if (scope === "filtered")
      return {
        body: { scope, filter: toExportFilter(filters) } satisfies ExportCreate,
        idempotencyKey,
      };
    if (scope === "selected")
      return { body: { scope, document_ids: selectedIds } satisfies ExportCreate, idempotencyKey };
    return { body: { scope } satisfies ExportCreate, idempotencyKey };
  }, [scope, filters, selectedIds]);

  useEffect(() => {
    reset();
    mutate({ body, idempotencyKey });
  }, [body, idempotencyKey, mutate, reset]);

  const exported = createExport.data;

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={texts["export.title"]}
      footer={
        <>
          <Button variant="tertiary" onClick={onClose}>
            {texts["common.cancel"]}
          </Button>
          {exported ? (
            <a
              href={exported.content_url}
              // No `download` attribute: the API answers with Content-Disposition: attachment, and
              // iOS WebKit ignores links that carry the attribute. Closed after the navigation starts.
              onClick={() => setTimeout(onClose, 0)}
              className={buttonClasses({ variant: "primary" })}
            >
              <span className="inline-flex items-center gap-2">
                <Download size={20} strokeWidth={1.75} aria-hidden />
                {t("export.download", { size: formatSize(exported.total_bytes) })}
              </span>
            </a>
          ) : (
            <Button
              icon={Download}
              loading={createExport.isPending}
              loadingText={texts["export.preparing"]}
              disabled={createExport.isError}
            >
              {texts["export.preparing"]}
            </Button>
          )}
        </>
      }
    >
      <RadioRowGroup aria-label={texts["export.title"]} value={scope} onValueChange={setScope}>
        <RadioRow
          value="all"
          title={texts["export.all"]}
          description={t("export.all.count", {
            n: total,
            документ: plural(total, plurals.документ),
          })}
        />
        <RadioRow
          value="filtered"
          title={texts["export.filtered"]}
          description={t("export.filtered.count", {
            n: matched,
            документ: plural(matched, plurals.документ),
          })}
          disabled={!filtered}
        />
        <RadioRow
          value="selected"
          title={texts["export.selected"]}
          description={
            selectedIds.length > 0
              ? t("export.selected.count", {
                  n: selectedIds.length,
                  документ: plural(selectedIds.length, plurals.документ),
                })
              : texts["export.selected.none"]
          }
          disabled={selectedIds.length === 0}
        />
      </RadioRowGroup>
      <div className="bg-sunken text-caption text-text2 flex items-start gap-3 rounded-lg p-3">
        <Archive size={16} strokeWidth={1.75} className="mt-0.5 shrink-0" aria-hidden />
        <div className="flex flex-col gap-0.5">
          <p className="text-label text-text">{texts["export.zip.title"]}</p>
          <p className="hidden md:block">{texts["export.zip.text"]}</p>
          <p className="md:hidden">{texts["export.zip.text.mobile"]}</p>
        </div>
      </div>
      {createExport.isError && (
        <Alert
          variant="danger"
          title={texts["export.failed"]}
          action={
            <Button variant="secondary" size="sm" onClick={() => mutate({ body, idempotencyKey })}>
              {texts["export.retry"]}
            </Button>
          }
        />
      )}
    </Dialog>
  );
}
