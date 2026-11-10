"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { DateInput } from "@/components/ui/date-input";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { type DocumentFilters, isRangeInvalid } from "@/lib/filters";
import { formatDate, parseDate } from "@/lib/format";
import { errorTitles, texts } from "@/lib/texts";

export type Period = Pick<DocumentFilters, "date_field" | "from" | "to">;

const DATE_FIELD_OPTIONS = [
  { value: "document", label: texts["filter.dateField.document"] },
  { value: "uploaded", label: texts["filter.dateField.uploaded"] },
] as const;

const DATE_LENGTH = "дд.мм.гггг".length;

/**
 * Typed text of one boundary. The filter changes only when the text is empty or a real day,
 * so a half-typed date does not reload the list.
 */
function useBoundary(value: string | null, onCommit: (iso: string | null) => void) {
  const [text, setText] = useState(value ? formatDate(value) : "");

  useEffect(() => {
    setText((current) => (parseDate(current) === value ? current : value ? formatDate(value) : ""));
  }, [value]);

  function change(next: string) {
    setText(next);
    if (next === "") onCommit(null);
    else if (parseDate(next)) onCommit(parseDate(next));
  }

  const invalid = text.length === DATE_LENGTH && parseDate(text) === null;
  return { text, change, error: invalid ? errorTitles.date_invalid : undefined };
}

/** «Фильтр по», «С», «По» of D07 and M04; a reversed range is shown and not applied (TC-039). */
export function PeriodFields({
  period,
  onChange,
  layout,
}: {
  period: Period;
  onChange: (patch: Partial<Period>) => void;
  layout: "row" | "sheet";
}) {
  const from = useBoundary(period.from, (iso) => onChange({ from: iso }));
  const to = useBoundary(period.to, (iso) => onChange({ to: iso }));
  const reversed = isRangeInvalid(period);

  return (
    <div className={layout === "row" ? "flex items-start gap-2" : "flex flex-col gap-4"}>
      <SegmentedControl
        label={texts["filter.dateField.label"]}
        options={DATE_FIELD_OPTIONS}
        value={period.date_field}
        onValueChange={(date_field) => onChange({ date_field })}
        fullWidth={layout === "sheet"}
      />
      <div className="flex flex-col gap-1.5">
        <div className="grid grid-cols-2 gap-2">
          <DateInput
            label={texts["filter.from"]}
            value={from.text}
            onChange={from.change}
            error={from.error ?? (reversed ? errorTitles.date_range_invalid : undefined)}
          />
          <DateInput
            label={texts["filter.to"]}
            value={to.text}
            onChange={to.change}
            error={to.error}
          />
        </div>
        {reversed && (
          <Button
            variant="tertiary"
            size="sm"
            onClick={() => onChange({ from: period.to, to: period.from })}
            className="self-start"
          >
            {texts["filter.rangeInvalid.swap"]}
          </Button>
        )}
      </div>
    </div>
  );
}
