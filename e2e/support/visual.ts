import { expect, type Locator, type Page } from "@playwright/test";

/**
 * Regions that differ between runs for reasons outside the UI: the browser's own PDF viewer,
 * live progress, and upload moments, which the server stamps with its real clock.
 */
function unstableRegions(page: Page): Locator[] {
  return [
    page.locator('iframe[title^="PDF"], object[type="application/pdf"], embed[type="application/pdf"]'),
    page.locator('[role="progressbar"]'),
    page.getByText(/^\d{2}\.\d{2}\.\d{4}, \d{2}:\d{2}$/),
    page.getByText(/^Загружен \d{2}\.\d{2}\.\d{4}/),
  ];
}

/**
 * TC-115: compares the page with the committed baseline `e2e/tests/visual/__snapshots__`.
 * A missing baseline fails the run; it is created only by `make visual-baseline` and reviewed by eye.
 */
export async function expectScreen(page: Page, name: string): Promise<void> {
  await page.evaluate(() => document.fonts.ready);
  // WebKit scrolls a sheet to its focused field by a few pixels more or less from run to run.
  await page.evaluate(() => {
    for (const element of document.querySelectorAll<HTMLElement>('[role="dialog"], [role="dialog"] *')) {
      if (element.scrollTop) element.scrollTop = 0;
    }
  });
  await expect(page).toHaveScreenshot(`${name}.png`, { fullPage: true, mask: unstableRegions(page) });
}

/**
 * Theme through the system preference, the default source of `data-theme` (FE-01), with reduced
 * motion so shimmer and row highlight are captured in their static state.
 */
export async function emulateStillTheme(page: Page, theme: "light" | "dark"): Promise<void> {
  await page.emulateMedia({ colorScheme: theme, reducedMotion: "reduce" });
}
