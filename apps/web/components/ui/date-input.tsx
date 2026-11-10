"use client";

import * as Popover from "@radix-ui/react-popover";
import {
  addDays,
  addMonths,
  format,
  isAfter,
  isSameDay,
  isSameMonth,
  parseISO,
  startOfMonth,
  startOfWeek,
} from "date-fns";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useRef, useState, type ChangeEvent, type KeyboardEvent } from "react";

import { formatDate, maskDate, parseDate } from "@/lib/format";
import { texts } from "@/lib/texts";

import { cn } from "./cn";
import { IconButton } from "./icon-button";
import { Input, type InputProps } from "./input";

export type DateInputProps = Omit<
  InputProps,
  "value" | "defaultValue" | "onChange" | "type" | "leading" | "trailing"
> & {
  /** Text as shown, `дд.мм.гггг` once complete; check it with `parseDate` from lib/format. */
  value: string;
  onChange: (value: string) => void;
  /** Latest day the calendar offers, `YYYY-MM-DD`; later days are disabled. */
  max?: string;
};

/**
 * Date field (FE-04): typing with the `дд.мм.гггг` mask comes first, the calendar in a popover
 * is the second way. Validation is the form's job, so errors show only after a save attempt.
 */
export function DateInput({ value, onChange, max, disabled, ...props }: DateInputProps) {
  const [open, setOpen] = useState(false);
  const frameRef = useRef<HTMLDivElement>(null);
  const selected = parseDate(value);

  function pick(isoDate: string) {
    onChange(formatDate(isoDate));
    setOpen(false);
  }

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Anchor virtualRef={frameRef} />
      <Input
        {...props}
        frameRef={frameRef}
        type="text"
        inputMode="numeric"
        autoComplete="off"
        maxLength={10}
        placeholder={texts["upload.date.placeholder"]}
        disabled={disabled}
        value={value}
        onChange={(event: ChangeEvent<HTMLInputElement>) => onChange(maskDate(event.target.value))}
        leading={
          <Popover.Trigger asChild>
            <IconButton
              size="sm"
              icon={CalendarDays}
              aria-label={texts["upload.date.calendar"]}
              disabled={disabled}
              className="-ml-2"
            />
          </Popover.Trigger>
        }
      />
      <Popover.Portal>
        <Popover.Content
          align="start"
          sideOffset={6}
          // Focus goes to the grid's current day, set by Calendar itself.
          onOpenAutoFocus={(event) => event.preventDefault()}
          className="animate-fade-in bg-raised shadow-3 z-50 rounded-xl p-3"
        >
          <Calendar selected={selected} max={max} onPick={pick} />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

const monthYearFormat = new Intl.DateTimeFormat("ru-RU", { month: "long", year: "numeric" });
const weekdayFormat = new Intl.DateTimeFormat("ru-RU", { weekday: "short" });
const dayLabelFormat = new Intl.DateTimeFormat("ru-RU", { dateStyle: "long" });

const ARROW_STEPS: Record<string, number> = {
  ArrowLeft: -1,
  ArrowRight: 1,
  ArrowUp: -7,
  ArrowDown: 7,
};

function Calendar({
  selected,
  max,
  onPick,
}: {
  selected: string | null;
  max?: string;
  onPick: (isoDate: string) => void;
}) {
  const maxDate = max ? parseISO(max) : null;
  const [active, setActive] = useState(() =>
    selected ? parseISO(selected) : (maxDate ?? new Date()),
  );
  const gridRef = useRef<HTMLTableElement>(null);
  // Focus the active day on open and after arrow keys, but not when the month buttons page.
  const focusActiveDay = useRef(true);
  const today = new Date();

  const firstShown = startOfWeek(startOfMonth(active), { weekStartsOn: 1 });
  const days = Array.from({ length: 42 }, (_, index) => addDays(firstShown, index));
  const weeks = Array.from({ length: 6 }, (_, week) => days.slice(week * 7, week * 7 + 7));
  const isDisabled = (day: Date) => maxDate !== null && isAfter(day, maxDate);

  useEffect(() => {
    if (!focusActiveDay.current) return;
    focusActiveDay.current = false;
    // Roving focus: the active day is the only tabbable cell.
    gridRef.current?.querySelector<HTMLButtonElement>('[tabindex="0"]')?.focus();
  }, [active]);

  function moveTo(day: Date) {
    focusActiveDay.current = true;
    setActive(day);
  }

  function handleKeyDown(event: KeyboardEvent) {
    const step = ARROW_STEPS[event.key];
    if (step !== undefined) moveTo(addDays(active, step));
    else if (event.key === "PageUp") moveTo(addMonths(active, -1));
    else if (event.key === "PageDown") moveTo(addMonths(active, 1));
    else return;
    event.preventDefault();
  }

  const previousMonth = addMonths(active, -1);
  const nextMonth = addMonths(active, 1);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        {/* No dictionary text for "previous/next month" yet: the target month names the button. */}
        <IconButton
          size="sm"
          icon={ChevronLeft}
          aria-label={monthYearFormat.format(previousMonth)}
          onClick={() => setActive(previousMonth)}
        />
        <p aria-live="polite" className="text-label first-letter:uppercase">
          {monthYearFormat.format(active)}
        </p>
        <IconButton
          size="sm"
          icon={ChevronRight}
          aria-label={monthYearFormat.format(nextMonth)}
          onClick={() => setActive(nextMonth)}
        />
      </div>
      <table ref={gridRef} className="border-collapse" onKeyDown={handleKeyDown}>
        <thead>
          <tr>
            {weeks[0]?.map((day) => (
              <th
                key={day.getDay()}
                scope="col"
                className="text-caption text-text3 pb-1 font-normal"
              >
                {weekdayFormat.format(day)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {weeks.map((week) => (
            <tr key={week[0]?.toISOString()}>
              {week.map((day) => (
                <td key={day.toISOString()} className="p-0">
                  <button
                    type="button"
                    tabIndex={isSameDay(day, active) ? 0 : -1}
                    disabled={isDisabled(day)}
                    aria-label={dayLabelFormat.format(day)}
                    aria-pressed={selected !== null && isSameDay(day, parseISO(selected))}
                    aria-current={isSameDay(day, today) ? "date" : undefined}
                    onClick={() => onPick(format(day, "yyyy-MM-dd"))}
                    className={cn(
                      "size-icon-button-sm text-body duration-fast rounded-md tabular-nums transition-colors",
                      "hover:bg-sunken disabled:text-disabled-text disabled:cursor-not-allowed disabled:hover:bg-transparent",
                      "aria-pressed:bg-primary aria-pressed:text-on-primary",
                      "aria-[current=date]:font-semibold",
                      !isSameMonth(day, active) && "text-text3",
                    )}
                  >
                    {day.getDate()}
                  </button>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
