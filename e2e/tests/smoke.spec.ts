import { expect, test } from "@playwright/test";

test("home page opens and renders in Medeo Sans", { tag: ["@b1"] }, async ({ page }) => {
  await page.goto("/");

  await expect(page.locator("html")).toHaveAttribute("lang", "ru");
  const loadedFamilies = await page.evaluate(async () => {
    await document.fonts.ready;
    return [...document.fonts]
      .filter((font) => font.status === "loaded")
      .map((font) => font.family.replaceAll('"', ""));
  });
  expect(loadedFamilies).toContain("Medeo Sans");
});
