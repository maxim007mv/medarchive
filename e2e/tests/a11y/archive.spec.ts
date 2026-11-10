import { expectNoSeriousA11yViolations } from "../../support/axe";
import { expect, test } from "../../support/fixtures";
import { sources } from "../../support/manifest";
import { emulateStillTheme } from "../../support/visual";
import { row, rows } from "../screens/helpers";

// The PDF viewer is the browser's own UI, not ours: axe does not see into it.
const PDF_VIEWER = 'iframe[title^="PDF"]';
const [bloodTest] = sources;

for (const theme of ["light", "dark"] as const) {
  test.describe(`TC-110 archive screens, ${theme}`, { tag: ["@b5", "@P0", "@TC-110"] }, () => {
    test.beforeEach(async ({ page, freshArchive }) => {
      await freshArchive.api.addAllSources();
      await emulateStillTheme(page, theme);
    });

    test("list D06/M02", async ({ page }, testInfo) => {
      await page.goto("/");
      await expect(rows(page)).toHaveCount(sources.length);

      await expectNoSeriousA11yViolations(page, testInfo);
    });

    test("nothing found D08/M05", async ({ page }, testInfo) => {
      await page.goto("/?q=рентген");
      await expect(page.getByRole("heading", { name: "Ничего не нашлось" })).toBeVisible();

      await expectNoSeriousA11yViolations(page, testInfo);
    });

    test("document and note D09/M06", async ({ page }, testInfo) => {
      await page.goto("/");
      await row(page, bloodTest.title).getByRole("link", { name: bloodTest.title }).click();
      await expect(page.getByRole("textbox", { name: "Заметка" })).toBeVisible();

      await expectNoSeriousA11yViolations(page, testInfo, { exclude: [PDF_VIEWER] });
    });
  });
}
