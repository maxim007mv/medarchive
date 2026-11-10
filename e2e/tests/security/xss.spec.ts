import { expect, test } from "../../support/fixtures";
import { sources } from "../../support/manifest";

const PAYLOAD = "<img src=x onerror=alert(1)>";

test("TC-095 a title with markup is shown as text and never executed", { tag: ["@b5", "@P0", "@TC-095"] }, async ({ page, freshArchive }) => {
  await freshArchive.api.addSource(sources[0], { title: PAYLOAD });
  const dialogs: string[] = [];
  page.on("dialog", async (dialog) => {
    dialogs.push(dialog.message());
    await dialog.dismiss();
  });

  await page.goto("/");
  const title = page.getByText(PAYLOAD, { exact: true }).first();
  await expect(title).toBeVisible();
  await title.click();
  await expect(page.getByRole("heading", { name: PAYLOAD })).toBeVisible();

  expect(await page.locator('img[src="x"]').count()).toBe(0);
  expect(dialogs).toEqual([]);
});
