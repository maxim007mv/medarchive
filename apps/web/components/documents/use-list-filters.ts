import { useQueryStates } from "nuqs";

import { DEFAULT_FILTERS, type DocumentFilters, filterParsers } from "@/lib/filters";

/** List filters in the URL (FE-14). Every change is a history entry, so «Назад» returns the previous one. */
export function useListFilters() {
  const [filters, setFilters] = useQueryStates(filterParsers, { history: "push" });

  const resetAll = () => setFilters({ ...DEFAULT_FILTERS });
  const removeDates = () =>
    setFilters({ from: null, to: null, date_field: DEFAULT_FILTERS.date_field });

  return { filters: filters satisfies DocumentFilters, setFilters, resetAll, removeDates };
}

export type ListFilters = ReturnType<typeof useListFilters>;
