import { expect, test } from "../../support/fixtures";
import { titlesInDefaultOrder } from "../../support/manifest";

import {
  expectCount,
  isPhone,
  rowTitles,
  rows,
  search,
  setPeriod,
  setType,
} from "./helpers";

/** Upload day of the seeded documents in Moscow, as the list filters by the user's zone. */
const moscowDay = (instant: string) =>
  new Intl.DateTimeFormat("ru-RU", {
    timeZone: "Europe/Moscow",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(instant));

test.describe("list, search and filters (FE-13..FE-15)", () => {
  // Seeding goes through upload, PDF checks and encryption: seconds per document.
  test.describe.configure({ timeout: 120_000 });

  let uploadedDay = "";

  test.beforeEach(async ({ page, freshArchive }) => {
    const created = await freshArchive.api.addAllSources();
    uploadedDay = moscowDay(String(created[0]?.uploaded_at));
    await page.goto("/");
    await expect(rows(page)).toHaveCount(6);
  });

  test(
    "TC-030 search «анализ» finds 2 of 6 with a chip",
    { tag: ["@b5", "@P0", "@TC-030"] },
    async ({ page }) => {
      await search(page, "анализ");

      await expectCount(page, 2, 6);
      expect(await rowTitles(page)).toEqual([
        "Общий анализ крови",
        "Биохимический анализ крови",
      ]);
      await expect(page.getByText("Поиск:")).toBeVisible();
      await expect(
        page.getByRole("button", { name: "Убрать фильтр «Поиск: анализ»" }),
      ).toBeVisible();
      await expect(page).toHaveURL(
        /q=%D0%B0%D0%BD%D0%B0%D0%BB%D0%B8%D0%B7|q=анализ/,
      );
    },
  );

  test(
    "TC-031 case does not matter",
    { tag: ["@b5", "@P0", "@TC-031"] },
    async ({ page }) => {
      for (const query of ["АНАЛИЗ", "Анализ"]) {
        await search(page, query);
        await expectCount(page, 2, 6);
        expect(await rowTitles(page)).toEqual([
          "Общий анализ крови",
          "Биохимический анализ крови",
        ]);
      }
    },
  );

  test(
    "TC-032 two characters show a hint and leave the list as is",
    { tag: ["@b5", "@P1", "@TC-032"] },
    async ({ page }) => {
      await search(page, "ан");

      await expect(page.getByText("Введите от 3 символов")).toBeVisible();
      await page.waitForTimeout(400);
      await expect(rows(page)).toHaveCount(6);
      await expect(page).not.toHaveURL(/q=/);
    },
  );

  test(
    "TC-033 nothing found for a query only: one «Сбросить поиск»",
    { tag: ["@b5", "@P0", "@TC-033"] },
    async ({ page }) => {
      await search(page, "рентген");

      const empty = page.getByRole("region", { name: "Ничего не нашлось" });
      await expect(empty).toBeVisible();
      await expect(
        empty.getByText(
          "По запросу «рентген» документов нет. Проверьте название или сбросьте поиск.",
        ),
      ).toBeVisible();
      await expect(empty.getByRole("button")).toHaveCount(1);
      await expect(
        empty.getByRole("button", { name: "Сбросить поиск" }),
      ).toBeVisible();

      await empty.getByRole("button", { name: "Сбросить поиск" }).click();
      await expect(rows(page)).toHaveCount(6);
    },
  );

  test(
    "TC-034 April by document date: 3 of 6 and the undated hint",
    { tag: ["@b5", "@P0", "@TC-034"] },
    async ({ page }) => {
      await setPeriod(page, { from: "01.04.2026", to: "30.04.2026" });

      await expectCount(page, 3, 6);
      expect(await rowTitles(page)).toEqual([
        "Заключение терапевта",
        "Общий анализ крови",
        "Биохимический анализ крови",
      ]);
      await expect(
        page.getByText(
          "1 документ без даты не участвует в фильтре по дате документа.",
        ),
      ).toBeVisible();
      await expect(
        page.getByRole("button", { name: "Показать его" }),
      ).toBeVisible();
    },
  );

  test(
    "TC-035 «Показать его» lists only the undated document with a «Без даты» chip",
    { tag: ["@b5", "@P0", "@TC-035"] },
    async ({ page }) => {
      await setPeriod(page, { from: "01.04.2026", to: "30.04.2026" });

      await page.getByRole("button", { name: "Показать его" }).click();

      await expect(page).toHaveURL(/undated=true/);
      await expect(rows(page)).toHaveCount(1);
      expect(await rowTitles(page)).toEqual(["ЭКГ покоя"]);
      await expect(
        page.getByRole("button", { name: "Убрать фильтр «Без даты»" }),
      ).toBeVisible();
      await expect(page).toHaveURL(/undated=true/);
    },
  );

  test(
    "TC-036 query and April: 2 of 6 without the undated hint",
    { tag: ["@b5", "@P0", "@TC-036"] },
    async ({ page }) => {
      await search(page, "анализ");
      await expectCount(page, 2, 6);
      await setPeriod(page, { from: "01.04.2026", to: "30.04.2026" });

      await expectCount(page, 2, 6);
      await expect(page.getByText(/без даты не участву/)).toHaveCount(0);
    },
  );

  test(
    "TC-037 upload date of today finds all six",
    { tag: ["@b5", "@P1", "@TC-037"] },
    async ({ page }) => {
      await setPeriod(page, {
        field: "Дата загрузки",
        from: uploadedDay,
        to: uploadedDay,
      });

      await expectCount(page, 6, 6);
    },
  );

  test(
    "TC-038 type «Заключение» gives 3 including ЭКГ покоя",
    { tag: ["@b5", "@P1", "@TC-038"] },
    async ({ page }) => {
      await setType(page, "Заключение");

      await expectCount(page, 3, 6);
      expect(await rowTitles(page)).toContain("ЭКГ покоя");
    },
  );

  test(
    "TC-039 start after end is shown and not applied",
    { tag: ["@b5", "@P0", "@TC-039"] },
    async ({ page }) => {
      const phone = isPhone(page);
      if (phone)
        await page.getByRole("button", { name: "Фильтр", exact: true }).click();
      const scope = phone
        ? page.getByRole("dialog", { name: "Фильтр" })
        : page.getByRole("main");

      await scope.getByLabel("С", { exact: true }).fill("30.04.2026");
      await scope.getByLabel("По", { exact: true }).fill("01.04.2026");

      await expect(scope.getByText("Начало периода позже конца")).toBeVisible();
      await expect(
        scope.getByRole("button", { name: "Поменять местами" }),
      ).toBeVisible();
      if (phone)
        await expect(
          scope.getByRole("button", { name: "Показать 6" }),
        ).toBeVisible();
      else await expect(rows(page)).toHaveCount(6);
      await expect(page.getByText(/^\d+ из 6$/)).toHaveCount(0);
    },
  );

  test(
    "TC-040 the filter survives reload and «Назад» returns the previous one",
    { tag: ["@b5", "@P1", "@TC-040"] },
    async ({ page }) => {
      await search(page, "анализ");
      await expectCount(page, 2, 6);
      await setType(page, "Анализ");
      await expect(page).toHaveURL(/type=analysis/);

      await page.reload();
      await expectCount(page, 2, 6);
      await expect(
        page.getByRole("searchbox", { name: "Поиск по названию" }),
      ).toHaveValue("анализ");

      await page.goBack();
      await expect(page).not.toHaveURL(/type=analysis/);
      await expect(page).toHaveURL(/q=/);
    },
  );

  test(
    "TC-041 «Сбросить всё» returns six documents and no chips",
    { tag: ["@b5", "@P1", "@TC-041"] },
    async ({ page }) => {
      await search(page, "анализ");
      await setType(page, "Анализ");
      await expectCount(page, 2, 6);

      await page
        .getByRole("main")
        .getByRole("button", { name: "Сбросить всё" })
        .click();

      await expect(rows(page)).toHaveCount(6);
      expect(await rowTitles(page)).toEqual(titlesInDefaultOrder);
      await expect(
        page.getByRole("button", { name: /^Убрать фильтр «/ }),
      ).toHaveCount(0);
    },
  );
});
