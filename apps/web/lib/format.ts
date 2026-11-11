// Number, date and name formats from docs/texts.md, section 2.

import { texts } from "./texts";

/** Between a number and its unit (docs/texts.md, section 1). */
const NBSP = "\u00a0";
const DEFAULT_TIME_ZONE = "Europe/Moscow";

/**
 * Russian plural form after `n`: `forms` are [one, few, many], e.g. `plurals.документ`
 * from lib/texts.ts: 1 документ, 2 документа, 5 документов, 11 документов, 21 документ.
 */
export function plural(n: number, forms: readonly [string, string, string]): string {
  const [one, few, many] = forms;
  const lastTwo = Math.abs(n) % 100;
  const last = lastTwo % 10;
  if (last === 1 && lastTwo !== 11) return one;
  if (last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14)) return few;
  return many;
}

/** Document date `YYYY-MM-DD` as `дд.мм.гггг`. A calendar date, so no time zone is involved. */
export function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-");
  return `${day}.${month}.${year}`;
}

/** Upload moment as `дд.мм.гггг, чч:мм` (24 h) in the user's time zone, Moscow by default. */
export function formatDateTime(instant: string | Date, timeZone = DEFAULT_TIME_ZONE): string {
  const parts = new Intl.DateTimeFormat("ru-RU", {
    timeZone,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(instant));
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((item) => item.type === type)?.value ?? "";
  return `${part("day")}.${part("month")}.${part("year")}, ${part("hour")}:${part("minute")}`;
}

/** `79 КБ` up to 999 КБ (at least 1), then megabytes with one decimal: `2,4 МБ`, `20 МБ`. */
export function formatSize(bytes: number): string {
  const kilobytes = Math.max(1, Math.round(bytes / 1000));
  if (kilobytes < 1000) return `${kilobytes}${NBSP}КБ`;
  const megabytes = Math.round(bytes / 100_000) / 10;
  return `${String(megabytes).replace(".", ",")}${NBSP}МБ`;
}

/**
 * Default document title from a file name (FE-12): without `.pdf` and leading digits, `-`
 * and `_` read as spaces, first letter capital. «01-general-blood-test.pdf» → «General blood
 * test». A name of digits and separators only gives «Документ» (`upload.name.fallback`).
 */
export function titleFromFileName(fileName: string): string {
  const words = fileName
    .replace(/\.pdf$/i, "")
    .replace(/^[\d\s_-]+/, "")
    .replace(/[\s_-]+/g, " ")
    .trim();
  if (!words) return texts["upload.name.fallback"];
  return words.charAt(0).toLocaleUpperCase("ru-RU") + words.slice(1);
}

/** Masks typed text as `дд.мм.гггг`: digits only, dots inserted after the day and the month. */
export function maskDate(input: string): string {
  const digits = input.replace(/\D/g, "").slice(0, 8);
  const day = digits.slice(0, 2);
  const month = digits.slice(2, 4);
  const year = digits.slice(4);
  return [day, month, year].filter(Boolean).join(".");
}

/** `дд.мм.гггг` of a real calendar day as `YYYY-MM-DD`; `null` for 31.02.2026 or partial input. */
export function parseDate(text: string): string | null {
  const match = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(text.trim());
  if (!match) return null;
  const [, day = "", month = "", year = ""] = match;
  const date = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day)));
  const isRealDay =
    date.getUTCFullYear() === Number(year) &&
    date.getUTCMonth() === Number(month) - 1 &&
    date.getUTCDate() === Number(day);
  return isRealDay ? `${year}-${month}-${day}` : null;
}
