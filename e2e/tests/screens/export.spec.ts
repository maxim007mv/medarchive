import { readFileSync } from "node:fs";

import type { Page } from "@playwright/test";

import { expect, test } from "../../support/fixtures";

import { rows, search } from "./helpers";

/** Entry names from the ZIP central directory (the export is stored, no external unzip needed). */
function zipEntries(zip: Buffer): string[] {
  const end = zip.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
  if (end < 0) throw new Error("not a ZIP: no end of central directory");
  const count = zip.readUInt16LE(end + 10);
  let offset = zip.readUInt32LE(end + 16);
  const names: string[] = [];
  for (let index = 0; index < count; index += 1) {
    const nameLength = zip.readUInt16LE(offset + 28);
    const extraLength = zip.readUInt16LE(offset + 30);
    const commentLength = zip.readUInt16LE(offset + 32);
    names.push(
      zip.subarray(offset + 46, offset + 46 + nameLength).toString("utf8"),
    );
    offset += 46 + nameLength + extraLength + commentLength;
  }
  return names;
}

async function downloadExport(
  page: Page,
  scopeName: string,
): Promise<{ fileName: string; entries: string[] }> {
  await page.getByRole("button", { name: "Экспорт" }).click();
  const dialog = page.getByRole("dialog", { name: "Выгрузить документы" });
  await dialog.getByRole("radio", { name: scopeName }).check();
  const download = page.waitForEvent("download");
  await dialog
    .getByRole("link", { name: /^Скачать ZIP · \d+(,\d)?\s(КБ|МБ)$/ })
    .click();
  const file = await download;
  return {
    fileName: file.suggestedFilename(),
    entries: zipEntries(readFileSync(await file.path())),
  };
}

test.describe("export (FE-20)", () => {
  // Seeding goes through upload, PDF checks and encryption: seconds per document.
  test.describe.configure({ timeout: 120_000 });

  test(
    "TC-070 the whole archive: six PDFs with transliterated names, CSV and JSON",
    { tag: ["@b6", "@P0", "@TC-070"] },
    async ({ page, freshArchive }) => {
      await freshArchive.api.addAllSources();
      await page.goto("/");
      await expect(rows(page)).toHaveCount(6);

      const { fileName, entries } = await downloadExport(page, "Весь архив");

      expect(fileName).toMatch(/^medarchive_\d{4}-\d{2}-\d{2}\.zip$/);
      expect(
        entries.filter((name) => name.startsWith("documents/")).sort(),
      ).toEqual(
        [
          "documents/2026-05-22_uzi-pochek-i-mochevogo-puzyrya.pdf",
          "documents/2026-05-21_lipidogramma.pdf",
          "documents/2026-04-10_zaklyuchenie-terapevta.pdf",
          "documents/2026-04-08_obshchiy-analiz-krovi.pdf",
          "documents/2026-04-08_biokhimicheskiy-analiz-krovi.pdf",
          "documents/bez-daty_ekg-pokoya.pdf",
        ].sort(),
      );
      expect(entries).toContain("documents.csv");
      expect(entries).toContain("documents.json");
      expect(entries).not.toContain("README.txt");
    },
  );

  test(
    "TC-071 «Только найденные» after a search has two PDFs",
    { tag: ["@b6", "@P0", "@TC-071"] },
    async ({ page, freshArchive }) => {
      await freshArchive.api.addAllSources();
      await page.goto("/");
      await search(page, "анализ");
      await expect(page.getByText("2 из 6", { exact: true })).toBeVisible();

      await page.getByRole("button", { name: "Экспорт" }).click();
      await expect(
        page.getByRole("radio", { name: "Только найденные" }),
      ).toBeChecked();
      await page.keyboard.press("Escape");
      const { entries } = await downloadExport(page, "Только найденные");

      expect(entries.filter((name) => name.endsWith(".pdf"))).toHaveLength(2);
    },
  );

  test(
    "TC-072 an empty archive cannot be exported and says why",
    { tag: ["@b6", "@P1", "@TC-072"] },
    async ({ page, freshArchive }) => {
      expect(freshArchive.workspaceId).toBeTruthy();
      await page.goto("/");

      const exportButton = page.getByRole("button", { name: "Экспорт" });
      await expect(exportButton).toHaveAttribute("aria-disabled", "true");
      await expect(exportButton).toHaveAccessibleDescription(
        "В архиве пока нет документов",
      );
    },
  );
});
