import type { Page } from "@playwright/test";

import { expect, test } from "../../support/fixtures";
import { sources } from "../../support/manifest";

import { rows, SAVE_TIMEOUT_MS, uploadDialog } from "./helpers";

const [bloodTest] = sources;

/** Presses Tab until the focused element matches, failing after `limit` presses. */
async function tabTo(
  page: Page,
  matches: () => Promise<boolean>,
  limit = 40,
): Promise<void> {
  for (let step = 0; step < limit; step += 1) {
    if (await matches()) return;
    await page.keyboard.press("Tab");
  }
  throw new Error("the element was not reached with Tab");
}

const focusedName = (page: Page) =>
  page.evaluate(() => {
    const element = document.activeElement as HTMLElement | null;
    return (
      // innerText skips the invisible loading copy of a Button label.
      element?.getAttribute("aria-label") ?? element?.innerText?.trim() ?? ""
    );
  });

async function expectVisibleFocus(page: Page): Promise<void> {
  const outline = await page.evaluate(
    () => getComputedStyle(document.activeElement as Element).outlineStyle,
  );
  expect(outline).not.toBe("none");
}

test.describe("keyboard and phone layout", () => {
  // Seeding goes through upload, PDF checks and encryption: seconds per document.
  test.describe.configure({ timeout: 120_000 });

  test(
    "TC-111 add, find, open and delete with the keyboard only",
    { tag: ["@b6", "@P0", "@TC-111"] },
    async ({ page, freshArchive }) => {
      await freshArchive.api.addSource(sources[1]!);
      await page.goto("/");
      await expect(rows(page)).toHaveCount(1);

      await tabTo(page, async () =>
        (await focusedName(page)).startsWith("Добавить PDF"),
      );
      await expectVisibleFocus(page);
      await page.keyboard.press("Enter");
      const dialog = uploadDialog(page);
      await expect(dialog).toBeVisible();
      const chooser = page.waitForEvent("filechooser");
      await tabTo(page, async () =>
        (await focusedName(page)).includes("Перетащите PDF сюда"),
      );
      await page.keyboard.press("Enter");
      await (await chooser).setFiles(bloodTest!.path);
      await expect(dialog.getByText("Готов к сохранению")).toBeVisible();

      await dialog.getByLabel("Название").focus();
      await page.keyboard.press("ControlOrMeta+A");
      await page.keyboard.type("Общий анализ крови");
      await page.keyboard.press("Tab");
      await page.keyboard.press("Space");
      await tabTo(
        page,
        async () =>
          (await page.evaluate(
            () => (document.activeElement as HTMLInputElement).placeholder,
          )) === "дд.мм.гггг",
      );
      await page.keyboard.type("08042026");
      await page.keyboard.press("Enter");
      await expect(
        page.getByText("Документ «Общий анализ крови» добавлен", {
          exact: true,
        }),
      ).toBeVisible({ timeout: SAVE_TIMEOUT_MS });

      await page.keyboard.press("/");
      await expect(
        page.getByRole("searchbox", { name: "Поиск по названию" }),
      ).toBeFocused();
      await page.keyboard.type("общий");
      await expect(rows(page)).toHaveCount(1);
      await tabTo(
        page,
        async () => (await focusedName(page)) === "Общий анализ крови",
      );
      await expectVisibleFocus(page);
      await page.keyboard.press("Enter");
      await expect(
        page.getByRole("heading", { name: "Общий анализ крови" }),
      ).toBeVisible();

      // Desktop panel has «Удалить документ»; the phone screen keeps it in «Ещё» (M06).
      const phone = (page.viewportSize()?.width ?? 1440) < 1024;
      await tabTo(
        page,
        async () =>
          (await focusedName(page)) === (phone ? "Ещё" : "Удалить документ"),
        60,
      );
      await page.keyboard.press("Enter");
      if (phone) await page.keyboard.press("Enter");
      const confirm = page.getByRole("dialog", { name: "Удалить документ?" });
      await expect(
        confirm.getByRole("button", { name: "Отмена" }),
      ).toBeFocused();
      await page.keyboard.press("Tab");
      await page.keyboard.press("Enter");

      await expect(
        page.getByText("Документ удалён", { exact: true }),
      ).toBeVisible();
      await expect(page).toHaveURL(/\/(\?.*)?$/);
    },
  );

  test.describe("390 px phone", () => {
    test.use({ viewport: { width: 390, height: 844 }, hasTouch: true });

    test(
      "TC-112 pinned «Добавить PDF» and sheet buttons keep clear of the bottom edge",
      { tag: ["@b6", "@P1", "@TC-112"] },
      async ({ page, freshArchive }) => {
        await freshArchive.api.addAllSources();
        // The sheet slides in; measured at rest.
        await page.emulateMedia({ reducedMotion: "reduce" });
        await page.goto("/");
        const bottomGap = async (name: string) =>
          page
            .getByRole("button", { name, exact: true })
            .last()
            .evaluate((element) => {
              const { bottom } = element.getBoundingClientRect();
              return window.innerHeight - bottom;
            });

        expect(await bottomGap("Добавить PDF")).toBeGreaterThanOrEqual(16);
        // The bar pads by the home indicator: env(safe-area-inset-bottom) is part of the rule.
        const padding = await page.evaluate(() =>
          [...document.styleSheets]
            .flatMap((sheet) => [...sheet.cssRules])
            .map((rule) => rule.cssText)
            .find((text) => text.includes(".pb-safe")),
        );
        expect(padding).toContain("safe-area-inset-bottom");

        await page.getByRole("button", { name: "Фильтр", exact: true }).click();
        await expect(
          page.getByRole("dialog", { name: "Фильтр" }),
        ).toBeVisible();
        expect(await bottomGap("Сбросить")).toBeGreaterThanOrEqual(16);
      },
    );
  });
});
