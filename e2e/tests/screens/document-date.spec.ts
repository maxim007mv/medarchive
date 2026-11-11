import { readFileSync } from "node:fs";

import type { Locator, Page } from "@playwright/test";

import { expect, test } from "../../support/fixtures";
import { sources } from "../../support/manifest";

import { isPhone, row, SAVE_TIMEOUT_MS, uploadDialog } from "./helpers";

const source = sources[0]!;
const fixtureBytes = readFileSync(source.path);
/** The fixtures carry the placeholder `D:20000101000000`, which the form skips. */
const PLACEHOLDER = "D:20000101000000";

/** The fixture under another name, or with a real creation date of the same length. */
function pdfPayload(name: string, creationDate?: string) {
  const text = fixtureBytes.toString("latin1");
  expect(text).toContain(PLACEHOLDER);
  const bytes = creationDate
    ? Buffer.from(text.replace(PLACEHOLDER, creationDate), "latin1")
    : fixtureBytes;
  return { name, mimeType: "application/pdf", buffer: bytes };
}

async function openWith(
  page: Page,
  file: ReturnType<typeof pdfPayload>,
): Promise<Locator> {
  await page.getByRole("button", { name: "Добавить PDF" }).first().click();
  const dialog = uploadDialog(page);
  await dialog.getByTestId("upload-file-input").setInputFiles(file);
  return dialog;
}

test.describe("document date in the form (owner's decision 11.11.2026)", () => {
  test.describe.configure({ timeout: 120_000 });

  test.beforeEach(async ({ page, freshArchive }) => {
    expect(freshArchive.workspaceId).toBeTruthy();
    await page.goto("/");
  });

  test(
    "TC-118 a date in the file name fills the field and is saved",
    { tag: ["@b4", "@P1", "@TC-118"] },
    async ({ page }) => {
      const dialog = await openWith(
        page,
        pdfPayload("2026-04-08_obshchiy-analiz-krovi.pdf"),
      );
      const date = dialog.getByLabel("Дата документа");

      await expect(date).toHaveValue("08.04.2026");
      await expect(
        dialog.getByText("Дата взята из имени файла, проверьте"),
      ).toBeVisible();
      await dialog.getByLabel("Название").fill("Общий анализ крови");
      await dialog.getByRole("radio", { name: "Анализ", exact: true }).click();
      await dialog.getByRole("button", { name: "Сохранить в архив" }).click();

      await expect(dialog).toBeHidden({ timeout: SAVE_TIMEOUT_MS });
      await expect(
        row(page, "Общий анализ крови").getByText("08.04.2026"),
      ).toBeVisible();
    },
  );

  test(
    "TC-118 /CreationDate fills the field when the name has no date; an edit hides the note",
    { tag: ["@b4", "@P1", "@TC-118"] },
    async ({ page }) => {
      const dialog = await openWith(
        page,
        pdfPayload("analiz.pdf", "D:20260410093000"),
      );
      const date = dialog.getByLabel("Дата документа");
      const note = dialog.getByText("Дата взята из свойств PDF, проверьте");

      await expect(date).toHaveValue("10.04.2026");
      await expect(note).toBeVisible();
      await date.fill("09.04.2026");
      await expect(note).toBeHidden();
    },
  );

  test(
    "TC-118 the placeholder creation date of the fixtures is not offered",
    { tag: ["@b4", "@P1", "@TC-118"] },
    async ({ page }) => {
      const dialog = await openWith(page, pdfPayload(source.fileName));

      await expect(dialog.getByText("Готов к сохранению")).toBeVisible({
        timeout: SAVE_TIMEOUT_MS,
      });
      await expect(dialog.getByLabel("Дата документа")).toHaveValue("");
      await expect(dialog.getByText(/^Дата взята из/)).toHaveCount(0);
    },
  );

  test(
    "TC-117 the «i» explains the document date on focus and tap; Esc closes only the explanation",
    { tag: ["@b4", "@P1", "@TC-117"] },
    async ({ page }) => {
      const dialog = await openWith(page, pdfPayload(source.fileName));
      const info = dialog.getByRole("button", {
        name: "Что это за дата",
      });
      const explanation = page.getByRole("tooltip");

      await info.focus();
      await expect(explanation).toContainText(
        "Дата, которая стоит в самом документе",
      );
      await expect(explanation).toContainText("По ней сортируется список");
      await page.keyboard.press("Escape");
      await expect(explanation).toBeHidden();
      await expect(info).toBeFocused();
      await expect(dialog).toBeVisible();

      await dialog.getByLabel("Название").focus();
      if (isPhone(page)) await info.tap();
      else await info.hover();
      await expect(explanation).toBeVisible();
    },
  );
});
