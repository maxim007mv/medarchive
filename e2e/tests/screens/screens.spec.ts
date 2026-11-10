import type { Page } from "@playwright/test";

import { expect, test } from "../../support/fixtures";
import { sources } from "../../support/manifest";
import { emulateStillTheme } from "../../support/visual";

import {
  fillDocumentForm,
  isPhone,
  openUpload,
  row,
  rows,
  saveScreen,
  search,
  setPeriod,
} from "./helpers";

// Not a gate: pictures for side-by-side review with MedArchive/02_design/screens (e2e/artifacts/screens).
// Run: pnpm --filter e2e exec playwright test tests/screens/screens.spec.ts

const [bloodTest] = sources;
const ecg = sources.find((source) => source.documentDate === null)!;

async function openList(page: Page) {
  await page.goto("/");
  await expect(rows(page)).toHaveCount(6);
}

for (const theme of ["light", "dark"] as const) {
  test.describe(`screens, ${theme}`, () => {
    // Seeding goes through upload, PDF checks and encryption: seconds per document.
    test.describe.configure({ timeout: 120_000 });

    test.beforeEach(async ({ page }) => emulateStillTheme(page, theme));

    test(`D01 onboarding, ${theme}`, async ({ page }, testInfo) => {
      await page.goto("/");
      await expect(
        page.getByRole("heading", {
          name: "Все медицинские документы в одном месте",
        }),
      ).toBeVisible();
      await saveScreen(page, testInfo, `D01-onboarding-${theme}`);
    });

    test(`D02..D04 upload form, ${theme}`, async ({
      page,
      freshArchive,
    }, testInfo) => {
      await freshArchive.api.addAllSources();
      await openList(page);
      const dialog = await openUpload(page, bloodTest!.path);
      await fillDocumentForm(dialog, {
        title: "Общий анализ крови",
        type: "analysis",
        documentDate: "2026-04-08",
      });
      await expect(dialog.getByText("Готов к сохранению")).toBeVisible();
      await saveScreen(page, testInfo, `D02-upload-${theme}`);

      await dialog.getByText("Дата не указана в документе").click();
      await saveScreen(page, testInfo, `D03-undated-${theme}`);

      await dialog.getByText("Дата не указана в документе").click();
      await dialog.getByLabel("Название").fill("");
      await dialog.getByLabel("Дата документа").fill("31.02.2026");
      await dialog.getByLabel("Название").press("Enter");
      await expect(
        dialog.getByText("Введите название документа"),
      ).toBeVisible();
      await saveScreen(page, testInfo, `D04-errors-${theme}`);
    });

    test(`D06 list, D07 period, D08 empty, ${theme}`, async ({
      page,
      freshArchive,
    }, testInfo) => {
      await freshArchive.api.addAllSources();
      await openList(page);
      await saveScreen(page, testInfo, `D06-list-${theme}`);

      await setPeriod(page, { from: "01.04.2026", to: "30.04.2026" });
      await expect(page.getByText("3 из 6", { exact: true })).toBeVisible();
      await saveScreen(page, testInfo, `D07-period-${theme}`);

      await search(page, "рентген");
      await expect(
        page.getByRole("heading", { name: "Ничего не нашлось" }),
      ).toBeVisible();
      await saveScreen(page, testInfo, `D08-empty-${theme}`);
    });

    test(`D09 document, D10 edit, D11 delete, ${theme}`, async ({
      page,
      freshArchive,
    }, testInfo) => {
      const created = await freshArchive.api.addAllSources();
      const blood = created.find((item) => item.title === bloodTest!.title)!;
      await freshArchive.api.send("PATCH", `/api/v1/documents/${blood.id}`, {
        data: {
          note: "Холестерин в биохимии выше нормы, пересдать в октябре.",
        },
        headers: { "If-Match": blood.etag },
      });
      await openList(page);
      await row(page, bloodTest!.title)
        .getByRole("link", { name: bloodTest!.title })
        .click();
      await expect(
        page.getByRole("textbox", { name: "Заметка" }),
      ).not.toHaveValue("");
      await saveScreen(page, testInfo, `D09-document-${theme}`);

      await page.getByRole("button", { name: "Изменить описание" }).click();
      await saveScreen(page, testInfo, `D10-edit-${theme}`);
      await page.getByRole("button", { name: "Отмена" }).click();

      if (isPhone(page)) {
        await page.getByRole("button", { name: "Ещё" }).click();
        await page.getByRole("menuitem", { name: "Удалить" }).click();
      } else {
        await page.getByRole("button", { name: "Удалить документ" }).click();
      }
      await expect(
        page.getByRole("dialog", { name: "Удалить документ?" }),
      ).toBeVisible();
      await saveScreen(page, testInfo, `D11-delete-${theme}`);
    });

    test(`D12 export, ${theme}`, async ({ page, freshArchive }, testInfo) => {
      await freshArchive.api.addAllSources();
      await openList(page);
      await search(page, "анализ");
      await expect(page.getByText("2 из 6", { exact: true })).toBeVisible();
      await page.getByRole("button", { name: "Экспорт" }).click();
      await expect(
        page.getByRole("link", { name: /^Скачать ZIP/ }),
      ).toBeVisible();
      await saveScreen(page, testInfo, `D12-export-${theme}`);
    });

    test(`D13 skeleton, D14 offline, ${theme}`, async ({
      page,
      context,
      freshArchive,
    }, testInfo) => {
      await freshArchive.api.addAllSources();
      await page.route("**/api/v1/documents?*", async (route) => {
        await new Promise((resolve) => setTimeout(resolve, 2500));
        await route.continue();
      });
      await page.goto("/");
      await expect(
        page.getByRole("status", { name: "Загружаем документы" }),
      ).toBeVisible();
      await saveScreen(page, testInfo, `D13-skeleton-${theme}`);
      await page.unroute("**/api/v1/documents?*");
      await expect(rows(page)).toHaveCount(6);

      await context.setOffline(true);
      await page.evaluate(() => window.dispatchEvent(new Event("offline")));
      await expect(
        page.getByText("Нет связи с сервером.", { exact: true }),
      ).toBeVisible();
      await saveScreen(page, testInfo, `D14-offline-${theme}`);
      await context.setOffline(false);
    });

    test(`settings, key and policy, ${theme}`, async ({
      page,
      freshArchive,
    }, testInfo) => {
      expect(freshArchive.accessKey).toBeTruthy();
      await page.goto("/settings");
      await expect(
        page.getByRole("heading", { name: "Хранение и доступ" }),
      ).toBeVisible();
      await saveScreen(page, testInfo, `settings-${theme}`);

      await page.goto("/policy");
      await saveScreen(page, testInfo, `policy-${theme}`);

      await page.goto("/restore");
      await saveScreen(page, testInfo, `restore-${theme}`);
    });

    test(`undated row, ${theme}`, async ({ page, freshArchive }, testInfo) => {
      await freshArchive.api.addSource(ecg);
      await page.goto("/");
      await expect(rows(page)).toHaveCount(1);
      await saveScreen(page, testInfo, `D06-undated-row-${theme}`);
    });
  });
}
