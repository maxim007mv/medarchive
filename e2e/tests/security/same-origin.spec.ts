import { expect, test } from "@playwright/test";

// SEC-01 (AGENTS.md, 152-ФЗ ст. 18 ч. 5): no external CDN, fonts or telemetry. Every request the
// page makes goes to its own origin; storage uploads are covered by the upload tests.
test("SEC-01 the page loads only same-origin resources", { tag: ["@b1"] }, async ({ page, baseURL }) => {
  const origin = new URL(baseURL ?? "").origin;
  const foreign: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.protocol === "data:" || url.protocol === "blob:") return;
    if (url.origin !== origin) foreign.push(url.origin);
  });

  await page.goto("/", { waitUntil: "networkidle" });

  expect(foreign).toEqual([]);
});
