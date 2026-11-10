import { browserTimeZone } from "@/lib/api/queries";
import { formatDateTime, parseDate } from "@/lib/format";

/** Today as `YYYY-MM-DD` in the browser's zone: a document cannot be dated later (TC-014). */
export function todayIso(now = new Date()): string {
  const [date = ""] = formatDateTime(now, browserTimeZone()).split(", ");
  return parseDate(date) ?? "";
}
