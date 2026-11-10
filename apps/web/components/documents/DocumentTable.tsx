"use client";

import { ChevronDown, Eye, FileText, StickyNote } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { MouseEvent } from "react";

import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/components/ui/cn";
import { TypeTag, UndatedTag } from "@/components/ui/tag";
import type { DocumentItem } from "@/lib/api/queries";
import type { OrderBy } from "@/lib/filters";
import { formatDate, formatDateTime, formatSize } from "@/lib/format";
import { t, texts } from "@/lib/texts";

import { RowMenu } from "./RowMenu";

export type ListProps = {
  items: DocumentItem[];
  timeZone: string;
  selected: ReadonlySet<string>;
  onToggle: (id: string, checked: boolean) => void;
  onDelete: (item: DocumentItem) => void;
  /** Row added just now: lit for 1,2 s where it stands, the list does not move (FE-13). */
  highlightId: string | null;
  deleteDisabledReason?: string;
};

export const documentHref = (id: string) => `/documents/${id}`;

/** Clicks on the row open the document; clicks on its own controls do not. */
export function isInsideControl(event: MouseEvent): boolean {
  return (
    (event.target as HTMLElement).closest("a, button, label, [role='checkbox'], [role='menu']") !==
    null
  );
}

function SortHeader({
  label,
  order,
  current,
  onOrderChange,
}: {
  label: string;
  order: OrderBy;
  current: OrderBy;
  onOrderChange: (order: OrderBy) => void;
}) {
  const active = order === current;
  return (
    <th scope="col" aria-sort={active ? "descending" : undefined} className="px-3 py-3 font-medium">
      <button
        type="button"
        onClick={() => onOrderChange(order)}
        className={cn(
          "inline-flex items-center gap-1 rounded-xs uppercase",
          active ? "text-text" : "hover:text-text",
        )}
      >
        {label}
        {active && <ChevronDown size={14} strokeWidth={1.75} aria-hidden />}
      </button>
    </th>
  );
}

export function FileMeta({ item }: { item: DocumentItem }) {
  return (
    <span className="text-caption text-text3 flex items-center gap-2">
      {t("list.row.meta", { size: formatSize(item.size_bytes) })}
      {item.has_note && (
        <span className="inline-flex items-center gap-1">
          <StickyNote size={12} strokeWidth={1.75} aria-hidden />
          {texts["list.row.hasNote"]}
        </span>
      )}
    </span>
  );
}

/** D06: semantic table from 1024 px; the whole row opens the document, the title link serves the keyboard. */
export function DocumentTable({
  items,
  timeZone,
  selected,
  onToggle,
  onDelete,
  highlightId,
  deleteDisabledReason,
  orderBy,
  onOrderChange,
}: ListProps & { orderBy: OrderBy; onOrderChange: (order: OrderBy) => void }) {
  const router = useRouter();
  const allSelected = items.length > 0 && items.every((item) => selected.has(item.id));
  const someSelected = !allSelected && items.some((item) => selected.has(item.id));

  return (
    <div className="border-border bg-surface shadow-1 overflow-x-auto rounded-xl border">
      <table className="w-full border-collapse text-left">
        <thead className="text-caption text-text3">
          <tr className="border-border border-b">
            <th scope="col" className="w-12 py-3 pl-4">
              <Checkbox
                aria-label={texts["list.selectAll"]}
                checked={allSelected ? true : someSelected ? "indeterminate" : false}
                onCheckedChange={(checked) =>
                  items.forEach((item) => onToggle(item.id, checked === true))
                }
              />
            </th>
            <th scope="col" className="px-3 py-3 font-medium uppercase">
              {texts["list.col.title"]}
            </th>
            <th scope="col" className="px-3 py-3 font-medium uppercase">
              {texts["list.col.type"]}
            </th>
            <SortHeader
              label={texts["list.col.documentDate"]}
              order="document_date desc"
              current={orderBy}
              onOrderChange={onOrderChange}
            />
            <SortHeader
              label={texts["list.col.uploadedAt"]}
              order="uploaded_at desc"
              current={orderBy}
              onOrderChange={onOrderChange}
            />
            <th scope="col" className="w-24">
              <span className="sr-only">{texts["list.row.more"]}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.id}
              data-testid="document-row"
              onClick={(event) => !isInsideControl(event) && router.push(documentHref(item.id))}
              className={cn(
                "border-border hover:bg-sunken cursor-pointer border-b last:border-b-0",
                item.id === highlightId && "motion-safe:animate-highlight",
              )}
            >
              <td className="py-3 pl-4">
                <Checkbox
                  aria-label={t("list.row.select", { title: item.title })}
                  checked={selected.has(item.id)}
                  onCheckedChange={(checked) => onToggle(item.id, checked === true)}
                />
              </td>
              <td className="px-3 py-3">
                <div className="flex items-center gap-3">
                  <span
                    className="size-icon-button-sm bg-sunken text-text2 grid shrink-0 place-items-center rounded-md"
                    aria-hidden
                  >
                    <FileText size={16} strokeWidth={1.75} />
                  </span>
                  <div className="flex min-w-0 flex-col gap-0.5">
                    <Link
                      href={documentHref(item.id)}
                      className="text-body truncate rounded-xs font-medium"
                    >
                      {item.title}
                    </Link>
                    <FileMeta item={item} />
                  </div>
                </div>
              </td>
              <td className="px-3 py-3">
                <TypeTag type={item.type} />
              </td>
              <td className="text-mono px-3 py-3 font-mono">
                {item.document_date ? formatDate(item.document_date) : <UndatedTag />}
              </td>
              <td className="text-mono text-text3 px-3 py-3 font-mono">
                {formatDateTime(item.uploaded_at, timeZone)}
              </td>
              <td className="py-3 pr-3">
                <div className="flex justify-end gap-1">
                  <Link
                    href={documentHref(item.id)}
                    tabIndex={-1}
                    aria-label={texts["list.row.open"]}
                    className="size-icon-button-sm text-text2 hover:bg-border hover:text-text grid place-items-center rounded-md"
                  >
                    <Eye size={16} strokeWidth={1.75} aria-hidden />
                  </Link>
                  <RowMenu onDelete={() => onDelete(item)} disabledReason={deleteDisabledReason} />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
