import {
  createLoader,
  createParser,
  createSerializer,
  parseAsArrayOf,
  parseAsBoolean,
  parseAsString,
  parseAsStringLiteral,
  type inferParserType,
} from "nuqs";

import type { components, operations } from "@/lib/api/schema";

export const DOCUMENT_TYPES = ["analysis", "conclusion", "other"] as const;
export type DocumentType = (typeof DOCUMENT_TYPES)[number];

const DATE_FIELDS = ["document", "uploaded"] as const;
export type DateField = (typeof DATE_FIELDS)[number];

const ORDERS = ["document_date desc", "uploaded_at desc"] as const;
export type OrderBy = (typeof ORDERS)[number];

/** The API rejects 1 or 2 non-space characters with 422, so shorter queries are never sent. */
export const MIN_QUERY_CHARS = 3;

const ISO_DAY = /^(\d{4})-(\d{2})-(\d{2})$/;

/** `YYYY-MM-DD` that names a real calendar day (no 2026-02-31). */
export function isIsoDay(value: string): boolean {
  const match = ISO_DAY.exec(value);
  if (!match) return false;
  const [, year, month, day] = match.map(Number) as [number, number, number, number];
  const date = new Date(Date.UTC(year, month - 1, day));
  return (
    date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day
  );
}

const parseAsIsoDay = createParser({
  parse: (value: string) => (isIsoDay(value) ? value : null),
  serialize: (value: string) => value,
});

/** URL state of the list (FE-14). Dates are ISO in the URL and `дд.мм.гггг` only in inputs. */
export const filterParsers = {
  q: parseAsString.withDefault(""),
  date_field: parseAsStringLiteral(DATE_FIELDS).withDefault("document"),
  from: parseAsIsoDay,
  to: parseAsIsoDay,
  type: parseAsArrayOf(parseAsStringLiteral(DOCUMENT_TYPES)).withDefault([]),
  order_by: parseAsStringLiteral(ORDERS).withDefault("document_date desc"),
  undated: parseAsBoolean.withDefault(false),
};

export type DocumentFilters = inferParserType<typeof filterParsers>;

export const DEFAULT_FILTERS: DocumentFilters = {
  q: "",
  date_field: "document",
  from: null,
  to: null,
  type: [],
  order_by: "document_date desc",
  undated: false,
};

/** `?q=…&from=…` for the given filters; defaults are left out of the URL. */
export const serializeFilters = createSerializer(filterParsers);
export const loadFilters = createLoader(filterParsers);

export function countQueryChars(q: string): number {
  return q.replace(/\s/g, "").length;
}

export function isSearchActive(q: string): boolean {
  return countQueryChars(q) >= MIN_QUERY_CHARS;
}

export function isRangeInvalid({ from, to }: Pick<DocumentFilters, "from" | "to">): boolean {
  return from !== null && to !== null && from > to;
}

/** Date filter that the list really applies: none while `undated` or while the range is reversed. */
export function hasAppliedDates(filters: DocumentFilters): boolean {
  return (
    !filters.undated && !isRangeInvalid(filters) && (filters.from !== null || filters.to !== null)
  );
}

export function hasAppliedFilters(filters: DocumentFilters): boolean {
  return (
    isSearchActive(filters.q) ||
    hasAppliedDates(filters) ||
    filters.type.length > 0 ||
    filters.undated
  );
}

type ListQuery = NonNullable<operations["documents.list"]["parameters"]["query"]>;

/** Query of `GET /api/v1/documents` for the filters; `tz` sets day boundaries for `date_field=uploaded`. */
export function toListQuery(filters: DocumentFilters, tz: string): ListQuery {
  const query: ListQuery = {};
  if (isSearchActive(filters.q)) query.q = filters.q.trim();
  if (filters.type.length > 0) query.type = filters.type;
  if (filters.undated) {
    query.undated = true;
  } else if (hasAppliedDates(filters)) {
    query.date_field = filters.date_field;
    if (filters.from) query.from = filters.from;
    if (filters.to) query.to = filters.to;
    if (filters.date_field === "uploaded") query.tz = tz;
  }
  if (filters.order_by !== DEFAULT_FILTERS.order_by) query.order_by = filters.order_by;
  return query;
}

/** The same conditions as the list, as the `filter` object of `POST /api/v1/exports`. */
export function toExportFilter(filters: DocumentFilters): components["schemas"]["DocumentFilter"] {
  const { q, type, date_field, from, to, undated } = toListQuery(filters, "");
  return { q, type, date_field, from, to, undated };
}
