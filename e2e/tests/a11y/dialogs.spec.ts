import type { Page } from "@playwright/test";

import { expectNoSeriousA11yViolations } from "../../support/axe";
import { expect, test } from "../../support/fixtures";
import { emulateStillTheme } from "../../support/visual";

const dialogs: { name: string; open: (page: Page) => Promise<void> }[] = [
  {
    name: "delete D11/M07",
    open: async (page) => {
      await page.getByText("Заключение терапевта").first().click();
      await page.getByRole("button", { name: /^Удалить( документ)?$/ }).click();
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
      await page.getByRole("button", { name: /Добавить/ }).first().click();
    },
  },
];

for (const theme of ["light", "dark"] as const) {
  for (const dialog of dialogs) {
    test(`TC-110 dialog ${dialog.name} has no serious violations, ${theme}`, { tag: ["@b6", "@P0", "@TC-110"] }, async ({ page, freshArchive }, testInfo) => {
      await freshArchive.api.addAllSources();
      await emulateStillTheme(page, theme);
      await page.goto("/");

      await dialog.open(page);
      await expect(page.getByRole("dialog")).toBeVisible();

      await expectNoSeriousA11yViolations(page, testInfo, { exclude: ['iframe[title^="PDF"]'] });
    });
  }
}
