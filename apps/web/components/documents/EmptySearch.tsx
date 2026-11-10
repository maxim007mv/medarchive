"use client";

import { Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { DocumentFilters } from "@/lib/filters";
import { texts } from "@/lib/texts";

import { type EmptyAction, emptySearch } from "./list-texts";

type Props = {
  filters: DocumentFilters;
  onResetSearch: () => void;
  onRemoveDates: () => void;
  onResetAll: () => void;
};

/** D08 / M05: what was searched and a way out. The parent renders it only after the server answered. */
export function EmptySearch({ filters, onResetSearch, onRemoveDates, onResetAll }: Props) {
  const { text, actions } = emptySearch(filters);
  const handlers: Record<EmptyAction, () => void> = {
    resetSearch: onResetSearch,
    removeDates: onRemoveDates,
    resetAll: onResetAll,
  };
  const labels: Record<EmptyAction, string> = {
    resetSearch: texts["empty.resetSearch"],
    removeDates: texts["empty.removeDates"],
    resetAll: texts["empty.resetAll"],
  };

  return (
    <section
      aria-labelledby="empty-search-title"
      className="border-border bg-surface shadow-1 flex flex-col items-center gap-4 rounded-xl border px-6 py-12 text-center"
    >
      <span
        className="size-icon-button bg-sunken text-text2 grid place-items-center rounded-lg"
        aria-hidden
      >
        <Search size={20} strokeWidth={1.75} />
      </span>
      <div className="flex max-w-md flex-col gap-2">
        <h2 id="empty-search-title" className="text-h3">
          {texts["empty.title"]}
        </h2>
        {text && <p className="text-text2">{text}</p>}
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        {actions.map((action, index) => (
          <Button
            key={action}
            variant={index === actions.length - 1 ? "primary" : "secondary"}
            onClick={handlers[action]}
          >
            {labels[action]}
          </Button>
        ))}
      </div>
    </section>
  );
}
