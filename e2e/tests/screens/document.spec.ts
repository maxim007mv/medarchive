import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

import { expect, test } from "../../support/fixtures";
import { sources } from "../../support/manifest";

import { isPhone, row, rowTitles, rows } from "./helpers";

const bySource = (title: string) =>
  sources.find((source) => source.title === title)!;

test.describe("document, note, edit, delete (FE-16..FE-19)", () => {
  test.beforeEach(async ({ page, freshArchive }) => {
    await freshArchive.api.addAllSources();
    await page.goto("/");
    await expect(rows(page)).toHaveCount(6);
  });

  test(
    "TC-050 a click anywhere on the row opens the document",
    { tag: ["@b5", "@P0", "@TC-050"] },
    async ({ page }) => {
      const target = row(page, "Общий анализ крови");
      await (
        isPhone(page)
          ? target.getByText("08.04.2026")
          : target.locator("td").nth(4)
      ).click();

      await expect(page).toHaveURL(/\/documents\/[0-9a-f-]{36}$/);
      await expect(
        page.getByRole("heading", { name: "Общий анализ крови" }),
      ).toBeVisible();
      await expect(page.getByText("Анализ", { exact: true })).toBeVisible();
      await expect(page.getByText("08.04.2026")).toBeVisible();
      await expect(
        page.getByText(/^\d{2}\.\d{2}\.\d{4}, \d{2}:\d{2}$/),
      ).toBeVisible();
      const viewer = page.locator('iframe[title="PDF: Общий анализ крови"]');
      await expect(
        viewer.or(page.getByText("Откройте PDF в новой вкладке")),
      ).toBeVisible();
    },
  );

  test(
    "TC-051 the note saves itself and survives a reload",
    { tag: ["@b6", "@P0", "@TC-051"] },
    async ({ page }) => {
      await row(page, "Общий анализ крови")
        .getByRole("link", { name: "Общий анализ крови" })
        .click();
      const note = page.getByRole("textbox", { name: "Заметка" });

      await note.fill("Холестерин выше нормы, пересдать в октябре.");

      await expect(
        page.getByRole("status").filter({ hasText: "Сохраняем…" }),
      ).toBeVisible();
      await expect(
        page.getByRole("status").filter({ hasText: "Сохранено" }),
      ).toBeVisible();
      await page.reload();
      await expect(page.getByRole("textbox", { name: "Заметка" })).toHaveValue(
        "Холестерин выше нормы, пересдать в октябре.",
      );
    },
  );

  test(
    "TC-052 the second tab gets a conflict and keeps its text",
    { tag: ["@b6", "@P0", "@TC-052"] },
    async ({ page, context }) => {
      await row(page, "Общий анализ крови")
        .getByRole("link", { name: "Общий анализ крови" })
        .click();
      const second = await context.newPage();
      await second.goto(page.url());
      await expect(
        second.getByRole("textbox", { name: "Заметка" }),
      ).toBeVisible();

      await page
        .getByRole("textbox", { name: "Заметка" })
        .fill("Из первой вкладки");
      await expect(
        page.getByRole("status").filter({ hasText: "Сохранено" }),
      ).toBeVisible();
      await second
        .getByRole("textbox", { name: "Заметка" })
        .fill("Из второй вкладки");

      await expect(
        second.getByText(
          "Документ изменился в другой вкладке. Обновите, чтобы увидеть новую версию",
        ),
      ).toBeVisible();
      await expect(
        second.getByRole("textbox", { name: "Заметка" }),
      ).toHaveValue("Из второй вкладки");
      await expect(
        second.getByRole("button", { name: "Обновить" }),
      ).toBeVisible();
    },
  );

  test(
    "TC-053 2001 characters are too long",
    { tag: ["@b6", "@P1", "@TC-053"] },
    async ({ page }) => {
      await row(page, "Общий анализ крови")
        .getByRole("link", { name: "Общий анализ крови" })
        .click();

      await page
        .getByRole("textbox", { name: "Заметка" })
        .fill("а".repeat(2001));

      await expect(
        page.getByText("Заметка длиннее 2000 символов"),
      ).toBeVisible();
      await expect(
        page.getByText("2001 / 2000 · сохраняется автоматически"),
      ).toBeVisible();
    },
  );

  test(
    "TC-054 dating ЭКГ покоя moves it between 21.05 and 10.04",
    { tag: ["@b6", "@P0", "@TC-054"] },
    async ({ page }) => {
      await row(page, "ЭКГ покоя")
        .getByRole("link", { name: "ЭКГ покоя" })
        .click();
      await page.getByRole("button", { name: "Изменить описание" }).click();

      await page.getByText("Дата не указана в документе").click();
      await page.getByLabel("Дата документа").fill("15.05.2026");
      await page
        .getByRole("button", { name: "Сохранить", exact: true })
        .click();
      await expect(
        page.getByRole("button", { name: "Изменить описание" }),
      ).toBeVisible();
      await page.getByRole("link", { name: "Все документы" }).click();

      const titles = await rowTitles(page);
      expect(titles.indexOf("ЭКГ покоя")).toBe(
        titles.indexOf("Липидограмма") + 1,
      );
      expect(titles.indexOf("Заключение терапевта")).toBe(
        titles.indexOf("ЭКГ покоя") + 1,
      );
      await expect(row(page, "ЭКГ покоя").getByText("Не указана")).toHaveCount(
        0,
      );
    },
  );

  test(
    "TC-055 delete with title and date, focus on «Отмена», then 5 documents",
    { tag: ["@b6", "@P0", "@TC-055"] },
    async ({ page }) => {
      await row(page, "Заключение терапевта")
        .getByRole("button", { name: "Ещё" })
        .click();
      await page.getByRole("menuitem", { name: "Удалить" }).click();

      const dialog = page.getByRole("dialog", { name: "Удалить документ?" });
      await expect(
        dialog.getByText(/«Заключение терапевта» от 10\.04\.2026/),
      ).toBeVisible();
      await expect(
        dialog.getByRole("button", { name: "Отмена" }),
      ).toBeFocused();
      await dialog
        .getByRole("button", { name: "Удалить", exact: true })
        .click();

      await expect(page.getByText("Документ удалён")).toBeVisible();
      await expect(rows(page)).toHaveCount(5);
      await page.reload();
      await expect(rows(page)).toHaveCount(5);
    },
  );

  test(
    "TC-056 Esc keeps the document and returns focus to the row menu",
    { tag: ["@b6", "@P1", "@TC-056"] },
    async ({ page }) => {
      const menu = row(page, "Заключение терапевта").getByRole("button", {
        name: "Ещё",
      });
      await menu.click();
      await page.getByRole("menuitem", { name: "Удалить" }).click();
      await expect(
        page.getByRole("dialog", { name: "Удалить документ?" }),
      ).toBeVisible();

      await page.keyboard.press("Escape");

      await expect(
        page.getByRole("dialog", { name: "Удалить документ?" }),
      ).toBeHidden();
      await expect(menu).toBeFocused();
      await expect(rows(page)).toHaveCount(6);
    },
  );

  test(
    "TC-060 Enter in the delete dialog does not delete",
    { tag: ["@b6", "@P0", "@TC-060"] },
    async ({ page }) => {
      const deletes: string[] = [];
      page.on(
        "request",
        (request) =>
          request.method() === "DELETE" && deletes.push(request.url()),
      );
      await row(page, "Заключение терапевта")
        .getByRole("button", { name: "Ещё" })
        .click();
      await page.getByRole("menuitem", { name: "Удалить" }).click();

      await page.keyboard.press("Enter");

      await expect(
        page.getByRole("dialog", { name: "Удалить документ?" }),
      ).toBeHidden();
      await expect(rows(page)).toHaveCount(6);
      expect(deletes).toEqual([]);
    },
  );

  test(
    "TC-057 «Скачать» gives the same bytes as the original",
    { tag: ["@b5", "@P0", "@TC-057"] },
    async ({ page }) => {
      const source = bySource("Общий анализ крови");
      await row(page, source.title)
        .getByRole("link", { name: source.title })
        .click();

      const download = page.waitForEvent("download");
      await page.getByRole("link", { name: "Скачать" }).click();
      const path = await (await download).path();

      const sha256 = createHash("sha256")
        .update(readFileSync(path))
        .digest("hex");
      expect(sha256).toBe(source.sha256);
    },
  );

  test(
    "TC-050 «Все документы» returns to the list with its filters",
    { tag: ["@b5", "@P0", "@TC-050"] },
    async ({ page }) => {
      await page
        .getByRole("searchbox", { name: "Поиск по названию" })
        .fill("анализ");
      await expect(page.getByText("2 из 6", { exact: true })).toBeVisible();
      await row(page, "Общий анализ крови")
        .getByRole("link", { name: "Общий анализ крови" })
        .click();

      await page.getByRole("link", { name: "Все документы" }).click();

      await expect(page).toHaveURL(/q=/);
      await expect(page.getByText("2 из 6", { exact: true })).toBeVisible();
    },
  );
});
