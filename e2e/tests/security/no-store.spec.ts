import { expect, test } from "../../support/fixtures";
import { sources } from "../../support/manifest";

// TC-094 web side (T16, shared computer): the server-rendered archive page carries titles,
// so the browser must not keep it in its cache either.
test("TC-094 the archive page is served with Cache-Control: no-store", { tag: ["@b5", "@P0", "@TC-094"] }, async ({ page, freshArchive }) => {
  await freshArchive.api.addSource(sources[0]);

  const response = await page.goto("/");

  expect(response?.headers()["cache-control"] ?? "").toContain("no-store");
});
