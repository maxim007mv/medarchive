"use client";

import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { DEFAULT_FILTERS, type DocumentFilters } from "@/lib/filters";
import { t, texts } from "@/lib/texts";

import { type ChipKey, filterChips } from "./list-texts";

const CLEARED: Record<ChipKey, Partial<DocumentFilters>> = {
  q: { q: "" },
  dates: { from: null, to: null, date_field: DEFAULT_FILTERS.date_field },
  type: { type: [] },
  undated: { undated: false },
};

/** D07: «3 из 6 ·», one chip per condition and «Сбросить всё» (FE-14, TC-041). */
export function AppliedFilters({
  filters,
  matched,
  total,
  onChange,
  onResetAll,
}: {
  filters: DocumentFilters;
  matched: number;
  total: number;
  onChange: (patch: Partial<DocumentFilters>) => void;
  onResetAll: () => void;
}) {
  const chips = filterChips(filters);
  if (chips.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <p role="status" className="text-caption text-text3 tabular-nums">
        {t("filter.count", { matched, total })}
      </p>
      {chips.map((chip) => (
        <Chip key={chip.key} text={chip.label} onRemove={() => onChange(CLEARED[chip.key])} />
      ))}
      <Button variant="tertiary" size="sm" onClick={onResetAll}>
        {texts["filter.resetAll"]}
      </Button>
    </div>
  );
}
