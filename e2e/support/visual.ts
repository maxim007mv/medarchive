import { expect, type Locator, type Page } from "@playwright/test";

/** Regions whose pixels are not the application's: the browser PDF viewer and live caret/progress. */
function unstableRegions(page: Page): Locator[] {
  return [
    page.locator('iframe[title^="PDF"], object[type="application/pdf"], embed[type="application/pdf"]'),
    page.locator('[role="progressbar"]'),
  ];
}

/**
 * TC-115: compares the page with the committed baseline `e2e/tests/visual/__snapshots__`.
 * A missing baseline fails the run; it is created only by `make visual-baseline` and reviewed by eye.
 */
export async function expectScreen(page: Page, name: string): Promise<void> {
  await page.evaluate(() => document.fonts.ready);
  await expect(page).toHaveScreenshot(`${name}.png`, { fullPage: true, mask: unstableRegions(page) });
}

/**
 * Theme through the system preference, the default source of `data-theme` (FE-01), with reduced
 * motion so shimmer and row highlight are captured in their static state.
 */
export async function emulateStillTheme(page: Page, theme: "light" | "dark"): Promise<void> {
  await page.emulateMedia({ colorScheme: theme, reducedMotion: "reduce" });
}
