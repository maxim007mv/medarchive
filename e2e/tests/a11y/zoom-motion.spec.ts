import type { Page } from "@playwright/test";

import { expect, test } from "../../support/fixtures";
import { sources } from "../../support/manifest";
import { row, rows } from "../screens/helpers";

const [bloodTest] = sources;

async function horizontalOverflowPx(page: Page): Promise<number> {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
}

// TC-113 and QA-07 step 3: 200% zoom of a 1280 px window is a 640 px wide CSS viewport; 320 px is
// the narrowest phone. The table (from 1024 px) may scroll inside itself, the page may not.
for (const width of [640, 320]) {
  test.describe(`TC-113 no horizontal scroll at ${width} px`, { tag: ["@b7", "@P1", "@TC-113"] }, () => {
    test.use({ viewport: { width, height: 800 } });

    test("onboarding, list and document", async ({ page, freshArchive }) => {
      await page.goto("/policy");
      expect(await horizontalOverflowPx(page), "/policy").toBeLessThanOrEqual(0);

      await freshArchive.api.addAllSources();
      await page.goto("/");
      await expect(rows(page)).toHaveCount(sources.length);
      expect(await horizontalOverflowPx(page), "list").toBeLessThanOrEqual(0);

      await row(page, bloodTest.title).getByRole("link", { name: bloodTest.title }).click();
      await expect(page.getByRole("heading", { level: 1, name: bloodTest.title })).toBeVisible();
      expect(await horizontalOverflowPx(page), "document").toBeLessThanOrEqual(0);
    });
  });
}

async function runningAnimations(page: Page): Promise<string[]> {
  return page.evaluate(() =>
    document
      .getAnimations()
      .filter((animation) => animation.playState === "running")
      .map((animation) => ("animationName" in animation ? String(animation.animationName) : "transition")),
  );
}

// TC-114 and QA-07 step 4: with reduced motion the skeleton does not shimmer and dialogs appear
// without movement.
test.describe("TC-114 prefers-reduced-motion", { tag: ["@b7", "@P1", "@TC-114"] }, () => {
  test.use({ reducedMotion: "reduce" });

  test("skeleton and dialog run no animation", async ({ page, freshArchive }) => {
    await freshArchive.api.addAllSources();
    const listDelayMs = 4000;
    await page.route("**/api/v1/documents?*", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, listDelayMs));
      await route.continue();
    });
    await page.goto("/");
    await expect(page.getByRole("status", { name: "Загружаем документы" })).toBeVisible();
    expect(await runningAnimations(page), "skeleton").toEqual([]);

    await page.unroute("**/api/v1/documents?*");
    await expect(rows(page)).toHaveCount(sources.length, { timeout: listDelayMs * 2 });
    await page.getByRole("button", { name: "Экспорт" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    expect(await runningAnimations(page), "dialog").toEqual([]);
  });
});
