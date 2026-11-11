// Document date guessed from the chosen PDF (docs/texts.md, section 7): the file name first,
// then `/CreationDate` of the PDF. Client only; the person checks the result in the form.

import { parseDate } from "./format";

export type DateGuess = { date: string; source: "fileName" | "pdf" };

const EARLIEST = "1900-01-01";
/** The Info dictionary sits near the start or the end of a PDF; the middle is page content. */
const SCAN_BYTES = 1024 * 1024;

/** Tried in this order. `(?:^|\D)…(?!\d)`: a date is not glued to other digits. */
const FILE_NAME_PATTERNS: Array<{ pattern: RegExp; order: "ymd" | "dmy" }> = [
  { pattern: /(?:^|\D)(\d{4})[-_.](\d{2})[-_.](\d{2})(?!\d)/g, order: "ymd" }, // 2026-04-08
  { pattern: /(?:^|\D)(\d{2})[-_.](\d{2})[-_.](\d{4})(?!\d)/g, order: "dmy" }, // 08.04.2026
  { pattern: /(?:^|\D)(\d{4})(\d{2})(\d{2})(?!\d)/g, order: "ymd" }, // 20260408
  { pattern: /(?:^|\D)(\d{2})[-_.](\d{2})[-_.](\d{2})(?!\d)/g, order: "dmy" }, // 08.04.26
];

/** `YYYY-MM-DD` of a real calendar day from 1900 up to `today`, else `null`. */
function acceptedDate(year: string, month: string, day: string, today: string): string | null {
  const iso = parseDate(`${day}.${month}.${year}`);
  return iso !== null && iso >= EARLIEST && iso <= today ? iso : null;
}

/** `26` is 2026 up to the current year, `98` is 1998. */
function fullYear(shortYear: string, today: string): string {
  return shortYear <= today.slice(2, 4) ? `20${shortYear}` : `19${shortYear}`;
}

/** `today` is `YYYY-MM-DD`; later dates are never returned. */
export function dateFromFileName(fileName: string, today: string): string | null {
  const name = fileName.replace(/\.pdf$/i, "");
  for (const { pattern, order } of FILE_NAME_PATTERNS) {
    for (const [, first = "", month = "", last = ""] of name.matchAll(pattern)) {
      const [year, day] = order === "ymd" ? [first, last] : [last, first];
      const date = acceptedDate(
        year.length === 2 ? fullYear(year, today) : year,
        month,
        day,
        today,
      );
      if (date) return date;
    }
  }
  return null;
}

/**
 * `/CreationDate (D:20260408…)` of a PDF's Info dictionary in the file read as Latin-1.
 * 1 January at 00:00:00 is skipped: reproducible-build tools write it as a placeholder
 * (all six task fixtures say `D:20000101000000`).
 */
export function dateFromPdfText(text: string, today: string): string | null {
  const match = /\/CreationDate\s*\(\s*D:(\d{4})(\d{2})(\d{2})(\d{6})?/.exec(text);
  if (!match) return null;
  const [, year = "", month = "", day = "", time = "000000"] = match;
  if (month === "01" && day === "01" && time === "000000") return null;
  return acceptedDate(year, month, day, today);
}

async function readLatin1(blob: Blob): Promise<string> {
  return new TextDecoder("latin1").decode(await blob.arrayBuffer());
}

export async function guessDocumentDate(file: File, today: string): Promise<DateGuess | null> {
  const fromName = dateFromFileName(file.name, today);
  if (fromName) return { date: fromName, source: "fileName" };
  const head = await readLatin1(file.slice(0, SCAN_BYTES));
  const tail = file.size > SCAN_BYTES ? await readLatin1(file.slice(-SCAN_BYTES)) : "";
  const fromPdf = dateFromPdfText(head, today) ?? dateFromPdfText(tail, today);
  return fromPdf ? { date: fromPdf, source: "pdf" } : null;
}
