import { CalendarDays } from "lucide-react";

import type { components } from "@/lib/api/schema";
import { texts } from "@/lib/texts";

import { cn } from "./cn";

export type DocumentType = components["schemas"]["DocumentCreate"]["type"];

const typeClasses: Record<DocumentType, string> = {
  analysis: "bg-analysis-bg text-analysis",
  conclusion: "bg-conclusion-bg text-conclusion",
  other: "bg-other-bg text-other",
};

const tagClasses =
  "inline-flex h-6 items-center gap-1.5 rounded-sm px-2 text-caption font-medium whitespace-nowrap";

/** Document type: colour and word together, never colour alone (brandbook §1.1). */
export function TypeTag({ type }: { type: DocumentType }) {
  return (
    <span className={cn(tagClasses, typeClasses[type])}>
      <span aria-hidden className="size-1.5 shrink-0 bg-current" />
      {texts[`type.${type}`]}
    </span>
  );
}

/** «Не указана» in the date column: amber with a calendar, so it does not read as missing data. */
export function UndatedTag() {
  return (
    <span className={cn(tagClasses, "bg-warn-bg text-warn")}>
      <CalendarDays size={14} strokeWidth={1.75} className="shrink-0" aria-hidden />
      {texts["list.row.noDate"]}
    </span>
  );
}
