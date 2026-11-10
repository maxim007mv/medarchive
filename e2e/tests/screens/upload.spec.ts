import type { Request } from "@playwright/test";

import { expect, test } from "../../support/fixtures";
import {
  generatedFixture,
  sources,
  titlesInDefaultOrder,
} from "../../support/manifest";

import {
  addThroughUi,
  fillDocumentForm,
  openUpload,
  row,
  rowTitles,
  rows,
  SAVE_TIMEOUT_MS,
} from "./helpers";

const [bloodTest] = sources;
const source = bloodTest!;

/** Requests seen by the page, to prove that a step sent nothing. */
function recordRequests(page: import("@playwright/test").Page): Request[] {
  const seen: Request[] = [];
  page.on("request", (request) => seen.push(request));
  return seen;
}

const isDocumentCreate = (request: Request) =>
  request.method() === "POST" && request.url().endsWith("/api/v1/documents");

test.describe("upload (FE-12)", () => {
  // Seeding goes through upload, PDF checks and encryption: seconds per document.
  test.describe.configure({ timeout: 120_000 });

  test.beforeEach(async ({ page, freshArchive }) => {
    expect(freshArchive.workspaceId).toBeTruthy();
    await page.goto("/");
  });

  test(
    "TC-010 saved document gets a toast, a lit row and the counter",
    { tag: ["@b4", "@P0", "@TC-010"] },
    async ({ page }) => {
      await addThroughUi(page, {
        ...source,
        title: "Общий анализ крови",
        type: "analysis",
        documentDate: "2026-04-08",
      });

      await expect(row(page, "Общий анализ крови")).toHaveClass(
        /animate-highlight/,
      );
      await expect(
        page.getByText(/^1 документ · отсортировано по дате документа/),
      ).toBeVisible();
      await expect(row(page, "Общий анализ крови")).not.toHaveClass(
        /animate-highlight/,
        { timeout: 3000 },
      );
    },
  );

  test(
    "TC-011 six documents line up by document date, undated last",
    { tag: ["@b4", "@P0", "@TC-011"] },
    async ({ page }) => {
      for (const item of sources) await addThroughUi(page, item);

      await expect(rows(page)).toHaveCount(6);
      expect(await rowTitles(page)).toEqual(titlesInDefaultOrder);
      await expect(
        row(page, "ЭКГ покоя").getByText("Не указана"),
      ).toBeVisible();
    },
  );

  test(
    "TC-012 empty title: button locked with a reason, Enter shows the error, nothing is sent",
    { tag: ["@b4", "@P0", "@TC-012"] },
    async ({ page }) => {
      const seen = recordRequests(page);
      const dialog = await openUpload(page, source.path);
      await expect(dialog.getByText("Готов к сохранению")).toBeVisible();
      const title = dialog.getByLabel("Название");

      await title.fill("");

      const save = dialog.getByRole("button", { name: "Сохранить в архив" });
      await expect(save).toHaveAttribute("aria-disabled", "true");
      await expect(
        dialog.getByText("Заполните название, чтобы сохранить"),
      ).toBeVisible();
      await title.press("Enter");
      await expect(
        dialog.getByText("Введите название документа"),
      ).toBeVisible();
      await expect(title).toBeFocused();
      expect(seen.filter(isDocumentCreate)).toHaveLength(0);
    },
  );

  test(
    "TC-013 31.02.2026 is not a date",
    { tag: ["@b4", "@P0", "@TC-013"] },
    async ({ page }) => {
      const dialog = await openUpload(page, source.path);
      await fillDocumentForm(dialog, {
        title: "Общий анализ крови",
        type: "analysis",
        documentDate: "2026-02-31",
      });

      await dialog.getByRole("button", { name: "Сохранить в архив" }).click();

      await expect(
        dialog.getByText("Такой даты нет. Проверьте день и месяц"),
      ).toBeVisible();
      await expect(dialog.getByLabel("Дата документа")).toBeFocused();
    },
  );

  test(
    "TC-014 tomorrow is refused and the document is not saved",
    { tag: ["@b4", "@P1", "@TC-014"] },
    async ({ page }) => {
      const seen = recordRequests(page);
      const dialog = await openUpload(page, source.path);
      await fillDocumentForm(dialog, {
        title: "Общий анализ крови",
        type: "analysis",
        documentDate: "2026-11-11",
      });

      await dialog.getByRole("button", { name: "Сохранить в архив" }).click();

      await expect(
        dialog.getByText("Дата документа не может быть позже сегодняшней"),
      ).toBeVisible();
      expect(seen.filter(isDocumentCreate)).toHaveLength(0);
    },
  );

  test(
    "TC-015 a PNG named .pdf is refused before any upload request",
    { tag: ["@b4", "@P0", "@TC-015"] },
    async ({ page }) => {
      const seen = recordRequests(page);
      const fake = generatedFixture("fake.pdf");

      const dialog = await openUpload(page, fake.path);

      await expect(
        dialog.getByText(
          "Файл не добавлен: это не PDF. Сохраните документ в PDF и попробуйте снова",
        ),
      ).toBeVisible();
      await expect(
        dialog.getByRole("button", { name: "Выбрать другой файл" }),
      ).toBeVisible();
      expect(
        seen.filter((request) => request.url().includes("/api/v1/uploads")),
      ).toHaveLength(0);
    },
  );

  test(
    "TC-016 over 20 МБ is refused with no request to the storage",
    { tag: ["@b4", "@P0", "@TC-016"] },
    async ({ page }) => {
      const seen = recordRequests(page);
      const big = generatedFixture("big-21mb.pdf");

      const dialog = await openUpload(page, big.path);

      await expect(
        dialog.getByText(
          "Файл больше 20 МБ. Сожмите PDF или разделите его на части",
        ),
      ).toBeVisible();
      expect(
        seen.filter((request) => request.method() === "POST"),
      ).toHaveLength(0);
    },
  );

  test(
    "TC-019 double click on save makes one document",
    { tag: ["@b4", "@P0", "@TC-019"] },
    async ({ page }) => {
      const dialog = await openUpload(page, source.path);
      await fillDocumentForm(dialog, {
        title: "Общий анализ крови",
        type: "analysis",
        documentDate: "2026-04-08",
      });

      await dialog
        .getByRole("button", { name: "Сохранить в архив" })
        .dblclick();

      await expect(
        page.getByText("Документ «Общий анализ крови» добавлен", {
          exact: true,
        }),
      ).toBeVisible({ timeout: SAVE_TIMEOUT_MS });
      await expect(rows(page)).toHaveCount(1);
      await page.reload();
      await expect(rows(page)).toHaveCount(1);
    },
  );

  test(
    "TC-020 a break during upload keeps the fields and «Повторить загрузку» finishes",
    { tag: ["@b4", "@P0", "@TC-020"] },
    async ({ page, baseURL }) => {
      // The only other origin the app talks to is the storage (CSP connect-src). The first
      // transfer is held while the person fills the form and presses save, then cut; the retry
      // goes through.
      const appOrigin = new URL(baseURL ?? "http://localhost:3000").origin;
      let cutNow!: () => void;
      const saved = new Promise<void>((resolve) => (cutNow = resolve));
      let held = false;
      await page.route(
        (url) => url.origin !== appOrigin,
        async (route) => {
          if (held) return route.continue();
          held = true;
          await saved;
          return route.abort("connectionreset");
        },
      );
      const dialog = await openUpload(page, source.path);
      await fillDocumentForm(dialog, {
        title: "Общий анализ крови",
        type: "analysis",
        documentDate: "2026-04-08",
      });
      await dialog.getByRole("button", { name: "Сохранить в архив" }).click();
      await expect(
        dialog.getByRole("button", { name: "Сохраняем…" }),
      ).toBeVisible();
      cutNow();

      await expect(
        dialog.getByText(/^Связь прервалась на \d+%$/),
      ).toBeVisible();
      await expect(
        dialog.getByText(
          "Введённые данные сохранены в форме. Повторите загрузку, когда появится интернет.",
        ),
      ).toBeVisible();
      await expect(dialog.getByLabel("Название")).toHaveValue(
        "Общий анализ крови",
      );
      await expect(dialog.getByLabel("Дата документа")).toHaveValue(
        "08.04.2026",
      );

      const retried = page.waitForResponse(
        (response) =>
          response.url().endsWith("/api/v1/uploads") &&
          response.status() === 201,
      );
      await dialog.getByRole("button", { name: "Повторить загрузку" }).click();
      await retried;

      await expect(
        page.getByText("Документ «Общий анализ крови» добавлен", {
          exact: true,
        }),
      ).toBeVisible({ timeout: SAVE_TIMEOUT_MS });
      await expect(rows(page)).toHaveCount(1);
    },
  );

  test(
    "TC-021 Esc asks «Закрыть без сохранения?» only when something was typed",
    { tag: ["@b4", "@P1", "@TC-021"] },
    async ({ page }) => {
      let dialog = await openUpload(page, source.path);
      await page.keyboard.press("Escape");
      await expect(dialog).toBeHidden();

      dialog = await openUpload(page, source.path);
      await dialog.getByLabel("Название").fill("Общий анализ крови");
      await page.keyboard.press("Escape");

      const confirm = page.getByRole("dialog", {
        name: "Закрыть без сохранения?",
      });
      await expect(confirm).toBeVisible();
      await confirm
        .getByRole("button", { name: "Продолжить заполнение" })
        .click();
      await expect(dialog.getByLabel("Название")).toHaveValue(
        "Общий анализ крови",
      );
    },
  );

  test(
    "TC-011 several files go one by one: «Файл 1 из 2»",
    { tag: ["@b4", "@P0", "@TC-011"] },
    async ({ page }) => {
      const [first, second] = sources;
      const dialog = await openUpload(page, [first!.path, second!.path]);

      await expect(dialog.getByText("Файл 1 из 2")).toBeVisible();
      await fillDocumentForm(dialog, first!);
      await dialog
        .getByRole("button", { name: "Сохранить и следующий" })
        .click();
      await expect(dialog.getByText("Файл 2 из 2")).toBeVisible();
      await fillDocumentForm(dialog, second!);
      await dialog.getByRole("button", { name: "Сохранить в архив" }).click();

      await expect(dialog).toBeHidden();
      await expect(rows(page)).toHaveCount(2);
    },
  );
});
