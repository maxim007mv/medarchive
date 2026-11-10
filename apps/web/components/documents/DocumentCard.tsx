"use client";

import { FileText } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { cn } from "@/components/ui/cn";
import { TypeTag, UndatedTag } from "@/components/ui/tag";
import { formatDate, formatDateTime } from "@/lib/format";
import { t, texts } from "@/lib/texts";

import { documentHref, isInsideControl, type ListProps } from "./DocumentTable";
import { RowMenu } from "./RowMenu";

/** M02: cards below 1024 px, the whole card opens the document. */
export function DocumentCards({
  items,
  timeZone,
  onDelete,
  highlightId,
  deleteDisabledReason,
}: ListProps) {
  const router = useRouter();

  return (
    <ul className="flex flex-col gap-2">
      {items.map((item) => (
        <li
          key={item.id}
          data-testid="document-card"
          onClick={(event) => !isInsideControl(event) && router.push(documentHref(item.id))}
          className={cn(
            "border-border bg-surface shadow-1 flex cursor-pointer items-start gap-3 rounded-xl border p-4",
            item.id === highlightId && "motion-safe:animate-highlight",
          )}
        >
          <span
            className="size-icon-button bg-sunken text-text2 grid shrink-0 place-items-center rounded-lg"
            aria-hidden
          >
            <FileText size={20} strokeWidth={1.75} />
          </span>
          <div className="flex min-w-0 flex-1 flex-col gap-2">
            <Link href={documentHref(item.id)} className="text-body-l rounded-xs font-medium">
              {item.title}
            </Link>
            <div className="flex flex-wrap items-center gap-2">
              <TypeTag type={item.type} />
              {item.document_date ? (
                <span className="text-mono font-mono">{formatDate(item.document_date)}</span>
              ) : (
                <UndatedTag />
              )}
            </div>
            <p className="text-caption text-text3">
              {t("list.card.uploaded", {
                date: formatDateTime(item.uploaded_at, timeZone).split(", ")[0] ?? "",
              })}
              {item.has_note && ` ${texts["list.card.hasNote"]}`}
            </p>
          </div>
          <RowMenu onDelete={() => onDelete(item)} disabledReason={deleteDisabledReason} />
        </li>
      ))}
    </ul>
  );
}
