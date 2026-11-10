/** Joins class names, skipping falsy ones. Callers pass layout classes only (width, margin). */
export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}
