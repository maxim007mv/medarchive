import type { Page } from "@playwright/test";

import { expect, test } from "../../support/fixtures";
import { sources } from "../../support/manifest";
import { emulateStillTheme, expectScreen } from "../../support/visual";
import { fillDocumentForm, isPhone, openUpload, row, rows, search, setPeriod } from "../screens/helpers";

// TC-115 (QA-06): every screen of 02_design/screens.md in both themes against the application's
// own baselines in __snapshots__/ (desktop project = D-screens, phone project = M-screens). The
// PNGs of MedArchive/02_design/screens are the reference for review by eye, not for pixels.
// D15 and D16 (AI suggestion) are out of scope (ADR-042).

const TAG = { tag: ["@b7", "@P1", "@TC-115"] };
const [bloodTest] = sources;

async function openList(page: Page): Promise<void> {
  await page.goto("/");
  await expect(rows(page)).toHaveCount(6);
}

for (const theme of ["light", "dark"] as const) {
  test.describe(`TC-115 screens, ${theme}`, TAG, () => {
    test.beforeEach(async ({ page }) => emulateStillTheme(page, theme));

    test(`D01 onboarding, ${theme}`, async ({ page }) => {
      await page.goto("/");
      await expect(page.getByRole("heading", { name: "Все медицинские документы в одном месте" })).toBeVisible();
      await expectScreen(page, `D01-onboarding-${theme}`);
    });

    test(`D02 form, D03 undated, D04 errors, ${theme}`, async ({ page, freshArchive }) => {
      await freshArchive.api.addAllSources();
      await openList(page);
      const dialog = await openUpload(page, bloodTest.path);
      await fillDocumentForm(dialog, { title: bloodTest.title, type: "analysis", documentDate: "2026-04-08" });
      await expect(dialog.getByText("Готов к сохранению")).toBeVisible();
      await expectScreen(page, `D02-upload-${theme}`);

      await dialog.getByText("Дата не указана в документе").click();
      await expectScreen(page, `D03-undated-${theme}`);

      await dialog.getByText("Дата не указана в документе").click();
      await dialog.getByLabel("Название").fill("");
      await dialog.getByLabel("Дата документа").fill("31.02.2026");
      await dialog.getByLabel("Название").press("Enter");
      await expect(dialog.getByText("Введите название документа")).toBeVisible();
      await expectScreen(page, `D04-errors-${theme}`);
    });

    test(`D06 list, D07 period, D08 nothing found, ${theme}`, async ({ page, freshArchive }) => {
      await freshArchive.api.addAllSources();
      await openList(page);
      await expectScreen(page, `D06-list-${theme}`);

      await setPeriod(page, { from: "01.04.2026", to: "30.04.2026" });
      await expect(page.getByText("3 из 6", { exact: true })).toBeVisible();
      await expectScreen(page, `D07-period-${theme}`);

      await search(page, "рентген");
      await expect(page.getByRole("heading", { name: "Ничего не нашлось" })).toBeVisible();
      await expectScreen(page, `D08-nothing-found-${theme}`);
    });

    test(`D09 document, D10 edit, D11 delete, ${theme}`, async ({ page, freshArchive }) => {
      const created = await freshArchive.api.addAllSources();
      const blood = created.find((item) => item.title === bloodTest.title);
      if (!blood) throw new Error("seed has no blood test");
      await freshArchive.api.send("PATCH", `/api/v1/documents/${blood.id}`, {
        data: { note: "Холестерин в биохимии выше нормы, пересдать в октябре." },
        headers: { "If-Match": blood.etag },
      });
      await openList(page);
      await row(page, bloodTest.title).getByRole("link", { name: bloodTest.title }).click();
      await expect(page.getByRole("textbox", { name: "Заметка" })).not.toHaveValue("");
      await expectScreen(page, `D09-document-${theme}`);

      await page.getByRole("button", { name: "Изменить описание" }).click();
      await expectScreen(page, `D10-edit-${theme}`);
      await page.getByRole("button", { name: "Отмена" }).click();

      if (isPhone(page)) {
        await page.getByRole("button", { name: "Ещё" }).click();
        await page.getByRole("menuitem", { name: "Удалить" }).click();
      } else {
        await page.getByRole("button", { name: "Удалить документ" }).click();
      }
      await expect(page.getByRole("dialog", { name: "Удалить документ?" })).toBeVisible();
      await expectScreen(page, `D11-delete-${theme}`);
    });

    test(`D12 export, ${theme}`, async ({ page, freshArchive }) => {
      await freshArchive.api.addAllSources();
      await openList(page);
      await search(page, "анализ");
      await expect(page.getByText("2 из 6", { exact: true })).toBeVisible();
      await page.getByRole("button", { name: "Экспорт" }).click();
      await expect(page.getByRole("link", { name: /^Скачать ZIP/ })).toBeVisible();
      await expectScreen(page, `D12-export-${theme}`);
    });

    test(`D13 skeleton, D14 offline, ${theme}`, async ({ page, context, freshArchive }) => {
      await freshArchive.api.addAllSources();
      // Long enough for toHaveScreenshot to see two equal frames of the skeleton (shown after 1 s).
      const listDelayMs = 8000;
      await page.route("**/api/v1/documents?*", async (route) => {
        await new Promise((resolve) => setTimeout(resolve, listDelayMs));
        await route.continue();
      });
      await page.goto("/");
      await expect(page.getByRole("status", { name: "Загружаем документы" })).toBeVisible();
      await expectScreen(page, `D13-skeleton-${theme}`);
      await page.unroute("**/api/v1/documents?*");
      await expect(rows(page)).toHaveCount(6, { timeout: listDelayMs * 2 });

      await context.setOffline(true);
      await page.evaluate(() => window.dispatchEvent(new Event("offline")));
      // Exact: disabled actions repeat the sentence in hidden descriptions (TC-085).
      await expect(page.getByText("Нет связи с сервером.", { exact: true })).toBeVisible();
      await expectScreen(page, `D14-offline-${theme}`);
      await context.setOffline(false);
    });
  });
}
