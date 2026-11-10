import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

import {
  expect,
  type Locator,
  type Page,
  type TestInfo,
} from "@playwright/test";

import type { DocumentType, SourceFixture } from "../../support/manifest";

/** `POST /documents` checks, encrypts and stores the PDF: seconds under parallel workers. */
export const SAVE_TIMEOUT_MS = 15_000;

const TYPE_LABELS: Record<DocumentType, string> = {
  analysis: "Анализ",
  conclusion: "Заключение",
  other: "Другое",
};

/** Desktop shows the table from 1024 px, phones the cards (FE-13). */
export function isPhone(page: Page): boolean {
  return (page.viewportSize()?.width ?? 1440) < 1024;
}

/** Rows of the list in the order shown: table rows or cards, whichever the width uses. */
export function rows(page: Page): Locator {
  return page.locator(
    isPhone(page)
      ? '[data-testid="document-card"]'
      : '[data-testid="document-row"]',
  );
}

export function row(page: Page, title: string): Locator {
  return rows(page).filter({
    has: page.getByRole("link", { name: title, exact: true }),
  });
}

/** Titles in display order; the title link is the first link of a row or card. */
export async function rowTitles(page: Page): Promise<string[]> {
  const titles: string[] = [];
  for (const item of await rows(page).all())
    titles.push(await item.getByRole("link").first().innerText());
  return titles;
}

/** `дд.мм.гггг` from `YYYY-MM-DD`. */
export function ru(isoDate: string): string {
  const [year, month, day] = isoDate.split("-");
  return `${day}.${month}.${year}`;
}

export function uploadDialog(page: Page): Locator {
  return page.getByRole("dialog", { name: "Новый документ" });
}

/** «Добавить PDF» → the idle dialog → the file goes into its input. */
export async function openUpload(
  page: Page,
  filePaths: string | string[],
): Promise<Locator> {
  await page.getByRole("button", { name: "Добавить PDF" }).first().click();
  const dialog = uploadDialog(page);
  await dialog.getByTestId("upload-file-input").setInputFiles(filePaths);
  return dialog;
}

export type DocumentInputUi = {
  title: string;
  type: DocumentType;
  documentDate: string | null;
};

/** Fills the form of the open upload dialog: title, type segment, date or «Дата не указана». */
export async function fillDocumentForm(
  dialog: Locator,
  input: DocumentInputUi,
): Promise<void> {
  const title = dialog.getByLabel("Название");
  await title.fill(input.title);
  await dialog
    .getByRole("radio", { name: TYPE_LABELS[input.type], exact: true })
    .click();
  if (input.documentDate)
    await dialog.getByLabel("Дата документа").fill(ru(input.documentDate));
  else await dialog.getByText("Дата не указана в документе").click();
}

/** Adds one source PDF through the UI and waits for the toast. */
export async function addThroughUi(
  page: Page,
  source: SourceFixture,
): Promise<void> {
  const dialog = await openUpload(page, source.path);
  await fillDocumentForm(dialog, source);
  await dialog.getByRole("button", { name: "Сохранить в архив" }).click();
  await expect(
    page.getByText(`Документ «${source.title}» добавлен`, { exact: true }),
  ).toBeVisible({ timeout: SAVE_TIMEOUT_MS });
  await expect(dialog).toBeHidden();
}

/** Period of the filter in the toolbar (desktop) or the filter sheet (phones, M04). */
export async function setPeriod(
  page: Page,
  {
    field = "Дата документа",
    from,
    to,
  }: { field?: "Дата документа" | "Дата загрузки"; from?: string; to?: string },
): Promise<void> {
  const scope = isPhone(page)
    ? await openFilterSheet(page)
    : page.locator("main");
  await scope.getByRole("radio", { name: field, exact: true }).click();
  if (from) await scope.getByLabel("С", { exact: true }).fill(from);
  if (to) await scope.getByLabel("По", { exact: true }).fill(to);
  if (isPhone(page)) await applyFilterSheet(page);
}

export async function setType(page: Page, label: string): Promise<void> {
  const scope = isPhone(page)
    ? await openFilterSheet(page)
    : page.locator("main");
  await scope.getByRole("radio", { name: label, exact: true }).click();
  if (isPhone(page)) await applyFilterSheet(page);
}

async function openFilterSheet(page: Page): Promise<Locator> {
  await page.getByRole("button", { name: "Фильтр", exact: true }).click();
  return page.getByRole("dialog", { name: "Фильтр" });
}

async function applyFilterSheet(page: Page): Promise<void> {
  const sheet = page.getByRole("dialog", { name: "Фильтр" });
  const apply = sheet.getByRole("button", { name: /^Показать \d+$/ });
  await expect(apply).not.toHaveAttribute("aria-busy", "true");
  await apply.click();
  await expect(sheet).toBeHidden();
}

export async function search(page: Page, query: string): Promise<void> {
  await page.getByRole("searchbox", { name: "Поиск по названию" }).fill(query);
}

export async function expectCount(
  page: Page,
  matched: number,
  total: number,
): Promise<void> {
  await expect(
    page.getByText(`${matched} из ${total}`, { exact: true }),
  ).toBeVisible();
}

const artifactsRoot = fileURLToPath(
  new URL("../../artifacts/screens/", import.meta.url),
);

/** Screenshot for manual comparison with MedArchive/02_design/screens (not a pixel gate). */
export async function saveScreen(
  page: Page,
  testInfo: TestInfo,
  name: string,
): Promise<void> {
  const directory = `${artifactsRoot}${testInfo.project.name}`;
  mkdirSync(directory, { recursive: true });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: `${directory}/${name}.png`,
    fullPage: false,
    animations: "disabled",
    caret: "hide",
  });
}
