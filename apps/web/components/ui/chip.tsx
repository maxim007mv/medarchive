import { X } from "lucide-react";

import { t } from "@/lib/texts";

export type ChipProps = {
  /** Dictionary text such as «Дата документа: 01.04.2026 – 30.04.2026». */
  text: string;
  onRemove: () => void;
};

/** Applied filter (FE-09). The part before «: » is the field and reads quieter than the value. */
export function Chip({ text, onRemove }: ChipProps) {
  const separator = text.indexOf(": ");
  const field = separator === -1 ? null : text.slice(0, separator + 1);
  const value = separator === -1 ? text : text.slice(separator + 2);

  return (
    <span className="border-border bg-surface text-label text-text inline-flex h-8 max-w-full items-center gap-1.5 rounded-full border pr-1.5 pl-3">
      {field && <span className="text-text3 shrink-0 font-normal">{field}</span>}
      <span className="min-w-0 truncate">{value}</span>
      <button
        type="button"
        aria-label={t("chip.remove", { chip: text })}
        onClick={onRemove}
        className="text-text2 duration-fast hover:bg-sunken hover:text-text grid size-6 shrink-0 place-items-center rounded-full transition-colors"
      >
        <X size={16} strokeWidth={1.75} aria-hidden />
      </button>
    </span>
  );
}
