import { expect, test } from "@playwright/test";

test("home page opens and renders in Medeo Sans", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { level: 1, name: "Медархив" })).toBeVisible();
  const loadedFamilies = await page.evaluate(async () => {
    await document.fonts.ready;
    return [...document.fonts]
      .filter((font) => font.status === "loaded")
      .map((font) => font.family.replaceAll('"', ""));
  });
  expect(loadedFamilies).toContain("Medeo Sans");
});
