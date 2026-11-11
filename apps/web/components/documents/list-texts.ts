import {
  type DocumentFilters,
  type DocumentType,
  hasAppliedDates,
  isSearchActive,
} from "@/lib/filters";
import { formatDate, plural } from "@/lib/format";
import { plurals, t, texts } from "@/lib/texts";

export const typeLabel = (type: DocumentType): string => texts[`type.${type}`];

export type ChipKey = "q" | "dates" | "type" | "undated";
export type FilterChip = { key: ChipKey; label: string };

function dateChip({ date_field, from, to }: DocumentFilters): string {
  const field = date_field === "document" ? "documentDate" : "uploaded";
  if (from && to) return t(`chip.${field}.range`, { from: formatDate(from), to: formatDate(to) });
  if (from) return t(`chip.${field}.from`, { from: formatDate(from) });
  return t(`chip.${field}.to`, { to: formatDate(to ?? "") });
}

/** Chips of AppliedFilters (FE-14) in the order of the toolbar: search, dates, type, undated. */
export function filterChips(filters: DocumentFilters): FilterChip[] {
  const chips: FilterChip[] = [];
  if (isSearchActive(filters.q))
    chips.push({ key: "q", label: t("chip.search", { q: filters.q.trim() }) });
  if (hasAppliedDates(filters)) chips.push({ key: "dates", label: dateChip(filters) });
  if (filters.type.length > 0) {
    chips.push({
      key: "type",
      label: t("chip.type", { types: filters.type.map(typeLabel).join(", ") }),
    });
  }
  if (filters.undated) chips.push({ key: "undated", label: texts["chip.undated"] });
  return chips;
}

export function documentCount(n: number): string {
  return `${n} ${plural(n, plurals.документ)}`;
}

/** «6 документов · отсортировано по дате документа, новые сверху» or «Найдено 3 документа». */
export function listSubtitle(
  filters: DocumentFilters,
  { total, matched }: { total: number; matched: number },
  filtered: boolean,
): string {
  if (filtered) {
    return t("list.subtitle.found", {
      Найден: plural(matched, plurals.найден),
      n: matched,
      документ: plural(matched, plurals.документ),
    });
  }
  const key =
    filters.order_by === "uploaded_at desc"
      ? "list.subtitle.byUploadedAt"
      : "list.subtitle.byDocumentDate";
  return t(key, { n: total, документ: plural(total, plurals.документ) });
}

/**
 * «1 документ без даты не участвует… Показать его»: the dictionary keeps it as one sentence whose
 * last two words are the button (docs/texts.md, section 9).
 */
export function undatedHint(n: number): { text: string; action: string } {
  const forms = ["undated.hint.one", "undated.hint.few", "undated.hint.many"] as const;
  const key = plural(n, forms) as (typeof forms)[number];
  const words = t(key, { n }).split(" ");
  return { text: words.slice(0, -2).join(" "), action: words.slice(-2).join(" ") };
}

/**
 * `{period}` of «Ничего не нашлось» exactly as docs/texts.md §10 defines it under the table. The
 * generator reads only table rows, so these three are not in lib/texts.ts yet (requested in
 * docs/progress/frontend-screens.md); replace with `t("empty.period.*")` once they are.
 */
const PERIOD = {
  range: (from: string, to: string) => `за ${from} – ${to}`,
  from: (from: string) => `с ${from}`,
  to: (to: string) => `по ${to}`,
};

function period({ from, to }: DocumentFilters): string {
  if (from && to) return PERIOD.range(formatDate(from), formatDate(to));
  if (from) return PERIOD.from(formatDate(from));
  return PERIOD.to(formatDate(to ?? ""));
}

export type EmptyAction = "resetSearch" | "removeDates" | "resetAll";

/**
 * Text and way out of an empty result (FE-15, docs/texts.md section 10): only a query gives
 * «Сбросить поиск»; dates give «Убрать фильтр по дате» and «Сбросить всё»; anything else «Сбросить всё».
 */
export function emptySearch(filters: DocumentFilters): {
  text: string | null;
  actions: EmptyAction[];
} {
  const hasQuery = isSearchActive(filters.q);
  const hasDates = hasAppliedDates(filters);
  const q = filters.q.trim();

  let text: string | null = null;
  if (hasQuery && hasDates) text = t("empty.text.queryPeriod", { q, period: period(filters) });
  else if (hasQuery) text = t("empty.text.query", { q });
  else if (hasDates) {
    const value = period(filters);
    text = t("empty.text.period", {
      Period: value.charAt(0).toLocaleUpperCase("ru-RU") + value.slice(1),
    });
  } else if (filters.type.length > 0) {
    text = t("empty.text.type", { types: filters.type.map(typeLabel).join(", ") });
  }

  const onlyQuery = hasQuery && !hasDates && filters.type.length === 0 && !filters.undated;
  const actions: EmptyAction[] = hasDates
    ? ["removeDates", "resetAll"]
    : onlyQuery
      ? ["resetSearch"]
      : ["resetAll"];
  return { text, actions };
}
