import { expectNoSeriousA11yViolations } from "../../support/axe";
import { expect, test } from "../../support/fixtures";
import { emulateStillTheme } from "../../support/visual";

for (const theme of ["light", "dark"] as const) {
  test(`TC-110 onboarding D01/M01 has no serious violations, ${theme}`, { tag: ["@b3", "@P0", "@TC-110"] }, async ({ page }, testInfo) => {
    await emulateStillTheme(page, theme);
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Все медицинские документы в одном месте" })).toBeVisible();

    await expectNoSeriousA11yViolations(page, testInfo);
  });

  test(`TC-110 policy page has no serious violations, ${theme}`, { tag: ["@b3", "@P0", "@TC-110"] }, async ({ page }, testInfo) => {
    await emulateStillTheme(page, theme);
    await page.goto("/policy");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    await expectNoSeriousA11yViolations(page, testInfo);
  });
}
