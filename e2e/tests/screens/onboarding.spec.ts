import { SESSION_COOKIE } from "../../support/archive";
import { expect, test } from "../../support/fixtures";
import { sources } from "../../support/manifest";

import { fillDocumentForm, SAVE_TIMEOUT_MS, uploadDialog } from "./helpers";

const [bloodTest] = sources;

test.describe("onboarding and consent (FE-11)", () => {
  // Seeding goes through upload, PDF checks and encryption: seconds per document.
  test.describe.configure({ timeout: 120_000 });

  test(
    "TC-001 clean profile shows D01 with the pick button locked until consent",
    { tag: ["@b3", "@P0", "@TC-001"] },
    async ({ page }) => {
      await page.goto("/");

      await expect(
        page.getByRole("heading", {
          name: "Все медицинские документы в одном месте",
        }),
      ).toBeVisible();
      await expect(
        page.getByRole("list").first().getByRole("listitem"),
      ).toHaveCount(3);
      await expect(
        page.getByRole("checkbox", {
          name: /Я соглашаюсь на обработку сведений о моём здоровье/,
        }),
      ).not.toBeChecked();
      const pick = page.getByRole("button", { name: "Выбрать первый PDF" });
      await expect(pick).toHaveAttribute("aria-disabled", "true");
      await expect(
        page.getByText("Отметьте согласие, чтобы выбрать файл"),
      ).toBeVisible();
      await expect(pick).toHaveAccessibleDescription(
        "Отметьте согласие, чтобы выбрать файл",
      );
      await expect(
        page.getByRole("link", {
          name: "Политика обработки персональных данных",
        }),
      ).toHaveAttribute("href", "/policy");
      await expect(
        page.getByRole("link", { name: "Уже есть архив? Открыть по ключу" }),
      ).toBeVisible();
    },
  );

  test(
    "TC-002 consent and the first PDF create the archive and open the form",
    { tag: ["@b3", "@P0", "@TC-002"] },
    async ({ page, context }) => {
      await page.goto("/");
      await page.getByRole("checkbox", { name: /Я соглашаюсь/ }).click();
      await expect(
        page.getByRole("button", { name: "Выбрать первый PDF" }),
      ).not.toHaveAttribute("aria-disabled", "true");

      const created = page.waitForResponse(
        (response) =>
          response.url().endsWith("/api/v1/workspaces") &&
          response.request().method() === "POST",
      );
      await page
        .getByTestId("onboarding-file-input")
        .setInputFiles(bloodTest!.path);

      expect((await created).status()).toBe(201);
      const dialog = uploadDialog(page);
      await expect(dialog).toBeVisible();
      await expect(dialog.getByText(bloodTest!.fileName)).toBeVisible();
      const cookie = (await context.cookies()).find(
        (item) => item.name === SESSION_COOKIE,
      );
      expect(cookie?.httpOnly).toBe(true);
    },
  );

  test(
    "TC-004 the access key is shown once in six groups of Medeo Mono",
    { tag: ["@b3", "@P1", "@TC-004"] },
    async ({ page }) => {
      await page.goto("/");
      await page.getByRole("checkbox", { name: /Я соглашаюсь/ }).click();
      await page
        .getByTestId("onboarding-file-input")
        .setInputFiles(bloodTest!.path);
      await expect(uploadDialog(page)).toBeVisible();

      await page.keyboard.press("Escape");

      const keyDialog = page.getByRole("dialog", {
        name: "Ключ доступа к архиву",
      });
      await expect(keyDialog).toBeVisible();
      const key = keyDialog.getByTestId("access-key");
      await expect(key).toHaveText(/^[0-9A-Z]{4}(-[0-9A-Z]{4}){5}$/);
      expect(
        await key.evaluate((element) => getComputedStyle(element).fontFamily),
      ).toContain("Medeo Mono");
      await expect(keyDialog.getByText("Показываем один раз")).toBeVisible();
      await expect(
        keyDialog.getByRole("button", { name: "Скопировать" }),
      ).toBeVisible();
      await expect(
        keyDialog.getByRole("button", { name: "Скачать как файл" }),
      ).toBeVisible();
    },
  );

  test(
    "TC-004 the first save hands over to the key dialog: one dialog, no toast over it, focus on the list after «Готово»",
    { tag: ["@b3", "@P1", "@TC-004"] },
    async ({ page }) => {
      await page.goto("/");
      await page.getByRole("checkbox", { name: /Я соглашаюсь/ }).click();
      await page
        .getByTestId("onboarding-file-input")
        .setInputFiles(bloodTest!.path);
      const upload = uploadDialog(page);
      await fillDocumentForm(upload, bloodTest!);
      await upload.getByRole("button", { name: "Сохранить в архив" }).click();

      const keyDialog = page.getByRole("dialog", {
        name: "Ключ доступа к архиву",
      });
      await expect(keyDialog).toBeVisible({ timeout: SAVE_TIMEOUT_MS });
      await expect(page.getByRole("dialog")).toHaveCount(1);
      const copy = keyDialog.getByRole("button", { name: "Скопировать" });
      await expect(copy).toBeFocused();
      // Its focus ring (2 px plus 2 px offset) must fit inside every box that clips it.
      const ringClipped = await copy.evaluate((button) => {
        const ring = button.getBoundingClientRect();
        for (let box = button.parentElement; box; box = box.parentElement) {
          if (getComputedStyle(box).overflow !== "visible") {
            const clip = box.getBoundingClientRect();
            if (
              ring.top - 4 < clip.top ||
              ring.bottom + 4 > clip.bottom ||
              ring.left - 4 < clip.left ||
              ring.right + 4 > clip.right
            )
              return true;
          }
          if (box.getAttribute("role") === "dialog") return false;
        }
        return false;
      });
      expect(ringClipped).toBe(false);
      const added = page.getByText(
        `Документ «${bloodTest!.title}» добавлен`,
        { exact: true },
      );
      await expect(added).toBeHidden();

      await keyDialog.getByRole("button", { name: "Готово" }).click();

      await expect(added).toBeVisible();
      await expect(
        page.getByRole("heading", { level: 1, name: "Документы" }),
      ).toBeFocused();
    },
  );

  test(
    "TC-001 the policy page opens from the consent link",
    { tag: ["@b3", "@P0", "@TC-001"] },
    async ({ page }) => {
      await page.goto("/");
      await page
        .getByRole("link", { name: "Политика обработки персональных данных" })
        .click();

      await expect(
        page.getByRole("heading", {
          level: 1,
          name: "Политика обработки персональных данных",
        }),
      ).toBeVisible();
      await expect(page.getByText("Версия от 10.11.2026")).toBeVisible();
    },
  );
});
