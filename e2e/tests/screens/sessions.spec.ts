import type { Browser, Page } from "@playwright/test";

import { expect, test } from "../../support/fixtures";
import { titlesInDefaultOrder } from "../../support/manifest";

import { rowTitles, rows } from "./helpers";

/** A browser profile with nothing in it: no cookie, so no archive. */
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

async function openByKey(page: Page, accessKey: string): Promise<void> {
  await page.goto("/restore");
  await page.getByLabel("Ключ доступа").fill(accessKey);
  await page.getByRole("button", { name: "Открыть архив" }).click();
}

const WRONG_KEY = "0000-0000-0000-0000-0000-0000";

test.describe("sessions and key (FE-10, FE-22)", () => {
  // TC-082 spends the login attempts of this IP, so the key tests run in this order, one by one.
  test.describe.configure({ mode: "serial" });

  test(
    "TC-080 the archive with notes is there after the browser is reopened",
    { tag: ["@b6", "@P0", "@TC-080"] },
    async ({ browser, context, freshArchive, baseURL }) => {
      const created = await freshArchive.api.addAllSources();
      const note = await freshArchive.api.send(
        "PATCH",
        `/api/v1/documents/${created[0]!.id}`,
        {
          data: { note: "Пересдать в октябре" },
          headers: { "If-Match": created[0]!.etag },
        },
      );
      expect(note.status()).toBe(200);
      const state = await context.storageState();

      const reopened = await browser.newContext({
        baseURL,
        storageState: state,
        locale: "ru-RU",
        timezoneId: "Europe/Moscow",
      });
      const page = await reopened.newPage();
      await page.goto("/");

      await expect(rows(page)).toHaveCount(6);
      expect(await rowTitles(page)).toEqual(titlesInDefaultOrder);
      await expect(page.getByText(/есть заметка/i)).toHaveCount(1);
      await reopened.close();
    },
  );

  test(
    "TC-081 a new profile opens the same archive by its key",
    { tag: ["@b6", "@P0", "@TC-081"] },
    async ({ browser, freshArchive, baseURL }) => {
      await freshArchive.api.addAllSources();
      const page = await cleanPage(browser, baseURL);

      await openByKey(
        page,
        freshArchive.accessKey.toLowerCase().replaceAll("-", ""),
      );

      await expect(rows(page)).toHaveCount(6);
      await page.context().close();
    },
  );

  test(
    "TC-083 a new key replaces the old one",
    { tag: ["@b6", "@P1", "@TC-083"] },
    async ({ page, browser, freshArchive, baseURL }) => {
      await page.goto("/settings");
      await page.getByRole("button", { name: "Выпустить новый ключ" }).click();
      await page
        .getByRole("dialog", { name: "Выпустить новый ключ?" })
        .getByRole("button", { name: "Выпустить" })
        .click();
      const keyDialog = page.getByRole("dialog", {
        name: "Ключ доступа к архиву",
      });
      const newKey =
        (await keyDialog.getByTestId("access-key").textContent()) ?? "";
      expect(newKey).not.toBe(freshArchive.accessKey);

      const other = await cleanPage(browser, baseURL);
      await openByKey(other, freshArchive.accessKey);
      await expect(
        other.getByText("Ключ не подошёл. Проверьте символы"),
      ).toBeVisible();
      await openByKey(other, newKey);
      await expect(other).toHaveURL(/\/$/);
      await other.context().close();
    },
  );

  test(
    "TC-084 deleting the archive needs the word «удалить» in any case",
    { tag: ["@b6", "@P0", "@TC-084"] },
    async ({ page, browser, freshArchive, baseURL }) => {
      await page.goto("/settings");
      const word = page.getByLabel(
        "Введите слово «удалить», чтобы подтвердить",
      );
      const submit = page.getByRole("button", { name: "Удалить архив" });

      await word.fill("удали");
      await expect(submit).toHaveAttribute("aria-disabled", "true");
      await word.fill("УДАЛИТЬ");
      await expect(submit).not.toHaveAttribute("aria-disabled", "true");
      await submit.click();

      await expect(
        page.getByText(
          /^Архив удалён\. Остатки данных будут стёрты до \d{2}\.\d{2}\.\d{4}, \d{2}:\d{2}$/,
        ),
      ).toBeVisible();
      expect((await page.request.get("/api/v1/session")).status()).toBe(401);
      const other = await cleanPage(browser, baseURL);
      await openByKey(other, freshArchive.accessKey);
      await expect(
        other.getByText("Ключ не подошёл. Проверьте символы"),
      ).toBeVisible();
      await other.context().close();
    },
  );

  test(
    "TC-082 five wrong keys get 401, the sixth 429 with a countdown",
    { tag: ["@b6", "@P0", "@TC-082"] },
    async ({ browser, baseURL }) => {
      const page = await cleanPage(browser, baseURL);
      const statuses: number[] = [];
      page.on(
        "response",
        (response) =>
          response.url().endsWith("/api/v1/sessions") &&
          statuses.push(response.status()),
      );
      await page.goto("/restore");
      const field = page.getByLabel("Ключ доступа");
      const submit = page.getByRole("button", { name: "Открыть архив" });

      for (let attempt = 1; attempt <= 6; attempt += 1) {
        await field.fill(
          `${WRONG_KEY.slice(0, -4)}${String(attempt).padStart(4, "0")}`,
        );
        const answered = page.waitForResponse((response) =>
          response.url().endsWith("/api/v1/sessions"),
        );
        await submit.click();
        // After 429 the button waits for Retry-After, so there is nothing more to send.
        if ((await answered).status() === 429) break;
      }

      // Earlier key tests of this run spend attempts of the same IP, so the limit may come sooner.
      const firstLimited = statuses.indexOf(429);
      expect(firstLimited).toBeGreaterThan(-1);
      expect(firstLimited).toBeLessThanOrEqual(5);
      expect(
        statuses.slice(0, firstLimited).every((status) => status === 401),
      ).toBe(true);
      expect(
        statuses.slice(firstLimited).every((status) => status === 429),
      ).toBe(true);
      await expect(
        page.getByText(
          /^Слишком много действий подряд\. Повторите через \d+ с$/,
        ),
      ).toBeVisible();
      await expect(
        page.getByRole("button", { name: "Открыть архив" }),
      ).toHaveAttribute("aria-disabled", "true");
      await page.context().close();
    },
  );

  test(
    "TC-085 losing the connection shows the banner and locks changes with a reason",
    { tag: ["@b5", "@P1", "@TC-085"] },
    async ({ page, context, freshArchive }) => {
      await freshArchive.api.addAllSources();
      await page.goto("/");
      await expect(rows(page)).toHaveCount(6);

      await context.setOffline(true);
      await page.evaluate(() => window.dispatchEvent(new Event("offline")));

      await expect(page.getByText("Нет связи с сервером.")).toBeVisible();
      await expect(
        page.getByText(
          "Показаны документы из последней загрузки. Изменения пока недоступны.",
        ),
      ).toBeVisible();
      const add = page.getByRole("button", { name: "Добавить PDF" }).first();
      await expect(add).toHaveAttribute("aria-disabled", "true");
      await expect(add).toHaveAccessibleDescription(
        "Нет связи с сервером. Действие станет доступно, когда связь восстановится",
      );
      await expect(rows(page)).toHaveCount(6);

      await context.setOffline(false);
      await page.evaluate(() => window.dispatchEvent(new Event("online")));
      await expect(page.getByText("Нет связи с сервером.")).toBeHidden();
    },
  );
});
