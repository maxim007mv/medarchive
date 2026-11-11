import type { Page } from "@playwright/test";

import { expectNoSeriousA11yViolations } from "../../support/axe";
import { expect, test } from "../../support/fixtures";
import { sources } from "../../support/manifest";
import { emulateStillTheme } from "../../support/visual";
import { isPhone, openUpload, row, rows } from "../screens/helpers";

const therapist = sources.find((source) => source.title === "Заключение терапевта");
const [bloodTest] = sources;

const dialogs: { name: string; open: (page: Page) => Promise<void> }[] = [
  {
    name: "delete D11/M07",
    open: async (page) => {
      if (!therapist) throw new Error("manifest has no «Заключение терапевта»");
      await row(page, therapist.title).getByRole("link", { name: therapist.title }).click();
      // The list's row menus are also «Ещё» until the document page replaces it.
      await expect(page.getByRole("textbox", { name: "Заметка" })).toBeVisible();
      if (isPhone(page)) {
        await page.getByRole("button", { name: "Ещё" }).click();
        await page.getByRole("menuitem", { name: "Удалить" }).click();
      } else {
        await page.getByRole("button", { name: "Удалить документ" }).click();
      }
    },
  },
  {
    name: "export D12/M08",
    open: async (page) => {
      await page.getByRole("button", { name: "Экспорт" }).click();
    },
  },
  {
    name: "new document D02/M03",
    open: async (page) => {
      await openUpload(page, bloodTest.path);
    },
  },
];

for (const theme of ["light", "dark"] as const) {
  for (const dialog of dialogs) {
    test(`TC-110 dialog ${dialog.name} has no serious violations, ${theme}`, { tag: ["@b6", "@P0", "@TC-110"] }, async ({ page, freshArchive }, testInfo) => {
      await freshArchive.api.addAllSources();
      await emulateStillTheme(page, theme);
      await page.goto("/");
      await expect(rows(page)).toHaveCount(sources.length);

      await dialog.open(page);
      await expect(page.getByRole("dialog")).toBeVisible();

      await expectNoSeriousA11yViolations(page, testInfo, { exclude: ['iframe[title^="PDF"]'] });
    });
  }
}
