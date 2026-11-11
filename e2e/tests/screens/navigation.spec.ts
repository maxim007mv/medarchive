import type { Browser, Locator, Page } from "@playwright/test";

import { expect, test } from "../../support/fixtures";
import { sources } from "../../support/manifest";

import { isPhone, row, rows, search } from "./helpers";

const ANALYSES = sources.filter((source) => source.title.includes("анализ"));

/** The list filtered to «анализ», so a return can be told from a plain `/`. */
async function openFilteredList(page: Page): Promise<void> {
  await page.goto("/");
  await search(page, "анализ");
  await expect(
    page.getByText(`${ANALYSES.length} из ${ANALYSES.length}`),
  ).toBeVisible();
}

/** Back by keyboard: focus the link, Enter. WebKit does not Tab to links without Option. */
async function goBackByKeyboard(link: Locator): Promise<void> {
  await expect(link).toBeVisible();
  await link.focus();
  await link.press("Enter");
}

async function expectFilteredList(page: Page): Promise<void> {
  await expect(page).toHaveURL(/\/\?q=/);
  await expect(rows(page)).toHaveCount(ANALYSES.length);
}

async function cleanPage(
  browser: Browser,
  baseURL: string | undefined,
): Promise<Page> {
  const context = await browser.newContext({
    baseURL,
    locale: "ru-RU",
    timezoneId: "Europe/Moscow",
  });
  return context.newPage();
}

test.describe("back to the list (TC-116, owner's decision 11.11.2026)", () => {
  test.describe.configure({ timeout: 120_000 });

  test.describe("with an archive", () => {
    test.beforeEach(async ({ freshArchive }) => {
      for (const source of ANALYSES) await freshArchive.api.addSource(source);
    });

    test(
      "TC-116 settings, open-by-key, policy, 404 and the document lead back to the filtered list",
      { tag: ["@b6", "@P0", "@TC-116"] },
      async ({ page }) => {
        const back = page.getByRole("link", { name: "К документам" });

        await openFilteredList(page);
        await page.getByRole("link", { name: "Хранение и доступ" }).click();
        await expect(
          page.getByRole("heading", { name: "Хранение и доступ", level: 1 }),
        ).toBeVisible();
        await goBackByKeyboard(back);
        await expectFilteredList(page);

        await page.getByRole("link", { name: "Хранение и доступ" }).click();
        await page
          .getByRole("link", { name: "Открыть архив по ключу" })
          .click();
        await expect(page).toHaveURL(/\/restore$/);
        await goBackByKeyboard(back);
        await expectFilteredList(page);

        for (const path of ["/policy", "/no-such-page"]) {
          await page.goto(path);
          await goBackByKeyboard(back);
          await expectFilteredList(page);
        }

        const title = ANALYSES[0]!.title;
        await row(page, title).getByRole("link", { name: title }).click();
        await expect(page.getByRole("heading", { name: title })).toBeVisible();
        await page.getByRole("button", { name: "Изменить описание" }).click();
        await goBackByKeyboard(back);
        await expectFilteredList(page);
      },
    );

    test(
      "TC-116 a missing document offers the way back",
      { tag: ["@b6", "@P1", "@TC-116"] },
      async ({ page }) => {
        await page.goto("/documents/00000000-0000-4000-8000-000000000000");

        await expect(
          page.getByRole("heading", {
            name: "Документ не найден. Возможно, он удалён",
          }),
        ).toBeVisible();
        await goBackByKeyboard(
          page.getByRole("link", { name: "К документам" }),
        );
        await expect(rows(page)).toHaveCount(ANALYSES.length);
      },
    );

    test(
      "TC-116 export and the phone filter sheet close back to the list with focus on their opener",
      { tag: ["@b6", "@P1", "@TC-116"] },
      async ({ page }) => {
        await openFilteredList(page);
        // Opened from the keyboard: WebKit does not focus a clicked button, so there would be no opener.
        const exportButton = page
          .getByRole("button", { name: "Экспорт" })
          .locator("visible=true");
        await exportButton.focus();
        await exportButton.press("Enter");
        const exportDialog = page.getByRole("dialog", {
          name: "Выгрузить документы",
        });
        await exportDialog.getByRole("button", { name: "Закрыть" }).click();
        await expect(exportDialog).toBeHidden();
        await expect(exportButton).toBeFocused();

        await exportButton.press("Enter");
        await expect(exportDialog).toBeVisible();
        await page.keyboard.press("Escape");
        await expect(exportDialog).toBeHidden();
        await expect(exportButton).toBeFocused();
        await expectFilteredList(page);

        if (!isPhone(page)) return;
        const filterButton = page.getByRole("button", {
          name: "Фильтр",
          exact: true,
        });
        await filterButton.focus();
        await filterButton.press("Enter");
        const sheet = page.getByRole("dialog", { name: "Фильтр" });
        await sheet.getByRole("button", { name: "Закрыть" }).click();
        await expect(sheet).toBeHidden();
        await expect(filterButton).toBeFocused();
      },
    );
  });

  test(
    "TC-116 before there is an archive «На главную» leads to the start page",
    { tag: ["@b6", "@P0", "@TC-116"] },
    async ({ browser, baseURL }) => {
      const page = await cleanPage(browser, baseURL);
      const onboarding = page.getByRole("heading", {
        name: "Все медицинские документы в одном месте",
      });

      await page.goto("/");
      await page
        .getByRole("link", { name: "Политика обработки персональных данных" })
        .click();
      await goBackByKeyboard(page.getByRole("link", { name: "На главную" }));
      await expect(onboarding).toBeVisible();

      for (const path of ["/restore", "/no-such-page"]) {
        await page.goto(path);
        await expect(
          page.getByRole("link", { name: "К документам" }),
        ).toHaveCount(0);
        await goBackByKeyboard(page.getByRole("link", { name: "На главную" }));
        await expect(onboarding).toBeVisible();
      }
      await page.context().close();
    },
  );
});
