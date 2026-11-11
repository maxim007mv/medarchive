"use client";

import { SlidersHorizontal } from "lucide-react";
import { useCallback, useRef, useState, type RefObject } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { IconButton } from "@/components/ui/icon-button";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { useDocumentCount } from "@/lib/api/queries";
import {
  DEFAULT_FILTERS,
  DOCUMENT_TYPES,
  type DocumentFilters,
  type DocumentType,
} from "@/lib/filters";
import { t, texts } from "@/lib/texts";

import { typeLabel } from "./list-texts";
import { PeriodFields } from "./PeriodFields";
import { SearchField } from "./SearchField";
import type { ListFilters } from "./use-list-filters";

type TypeChoice = DocumentType | "all";

function typeOptions(allLabel: string) {
  return [
    { value: "all" as const, label: allLabel },
    ...DOCUMENT_TYPES.map((type) => ({ value: type, label: typeLabel(type) })),
  ];
}

/** One type or all: the segment cannot show two (a URL with several types selects no segment). */
function typeChoice(types: DocumentType[]): TypeChoice | undefined {
  if (types.length === 0) return "all";
  return types.length === 1 ? types[0] : undefined;
}

const typesOf = (choice: TypeChoice): DocumentType[] => (choice === "all" ? [] : [choice]);

/** Search, period and type above the list: one row from 1024 px (D06), search + sheet below (M04). */
export function Toolbar({ filters, setFilters }: Pick<ListFilters, "filters" | "setFilters">) {
  const [sheetOpen, setSheetOpen] = useState(false);
  const filterOpenerRef = useRef<HTMLElement | null>(null);
  const commitQuery = useCallback((q: string) => void setFilters({ q }), [setFilters]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start gap-2 lg:gap-4">
        <div className="min-w-0 flex-1 lg:max-w-xs lg:pt-6">
          <SearchField value={filters.q} onCommit={commitQuery} />
        </div>
        <div className="hidden items-start gap-4 lg:flex">
          <PeriodFields
            period={filters}
            onChange={(patch) => void setFilters({ ...patch, undated: false })}
            layout="row"
          />
        </div>
        <div className="ml-auto hidden pt-6 lg:block">
          <SegmentedControl
            aria-label={texts["upload.type.label"]}
            options={typeOptions(texts["filter.type.all"])}
            value={typeChoice(filters.type)}
            onValueChange={(choice) => void setFilters({ type: typesOf(choice) })}
          />
        </div>
        <IconButton
          icon={SlidersHorizontal}
          variant="outline"
          aria-label={texts["filter.sheet.title"]}
          onClick={(event) => {
            filterOpenerRef.current = event.currentTarget;
            setSheetOpen(true);
          }}
          className="lg:hidden"
        />
      </div>
      {sheetOpen && (
        <FilterSheet
          filters={filters}
          finalFocus={filterOpenerRef}
          onApply={(next) => {
            void setFilters(next);
            setSheetOpen(false);
          }}
          onClose={() => setSheetOpen(false)}
        />
      )}
    </div>
  );
}

/** M04: changes stay a draft until «Показать N»; N comes live from `page_size=1`. */
function FilterSheet({
  filters,
  finalFocus,
  onApply,
  onClose,
}: {
  filters: DocumentFilters;
  finalFocus?: RefObject<HTMLElement | null>;
  onApply: (next: Partial<DocumentFilters>) => void;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState(filters);
  const count = useDocumentCount(draft, { enabled: true });
  const update = (patch: Partial<DocumentFilters>) =>
    setDraft((current) => ({ ...current, ...patch }));
  const reset = {
    date_field: DEFAULT_FILTERS.date_field,
    from: null,
    to: null,
    type: [],
    undated: false,
  };

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={texts["filter.sheet.title"]}
      finalFocus={finalFocus}
      footer={
        <>
          <Button variant="secondary" onClick={() => setDraft({ ...draft, ...reset })}>
            {texts["filter.resetShort"]}
          </Button>
          <Button
            loading={count.data === undefined}
            onClick={() =>
              onApply({
                date_field: draft.date_field,
                from: draft.from,
                to: draft.to,
                type: draft.type,
                undated: draft.undated,
              })
            }
          >
            {t("filter.sheet.apply", { n: count.data ?? 0 })}
          </Button>
        </>
      }
    >
      <PeriodFields
        period={draft}
        onChange={(patch) => update({ ...patch, undated: false })}
        layout="sheet"
      />
      <SegmentedControl
        label={texts["upload.type.label"]}
        options={typeOptions(texts["filter.type.all.mobile"])}
        value={typeChoice(draft.type)}
        onValueChange={(choice) => update({ type: typesOf(choice) })}
        fullWidth
      />
    </Dialog>
  );
}
