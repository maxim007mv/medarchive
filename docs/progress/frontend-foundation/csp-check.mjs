// Loads pages of a production build and reports CSP violations and console errors.
// Run from the repo root with `next start` up: BASE_URL=http://localhost:3300 node docs/progress/frontend-foundation/csp-check.mjs
import { createRequire } from "node:module";

const require = createRequire(new URL("../../../e2e/package.json", import.meta.url));
const { chromium } = require("@playwright/test");

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3300";
const browser = await chromium.launch();
const page = await browser.newPage();
const problems = [];
page.on("console", (message) => {
  if (message.type() === "error") problems.push(message.text().slice(0, 200));
});
await page.exposeFunction("reportViolation", (text) => problems.push(`CSP ${text}`));
await page.addInitScript(() => {
  document.addEventListener("securitypolicyviolation", (event) =>
    window.reportViolation(`${event.violatedDirective} ${event.blockedURI}`),
  );
});

for (const path of ["/policy", "/no-such-page", "/ui"]) {
  const response = await page.goto(`${BASE_URL}${path}`, { waitUntil: "networkidle" });
  const theme = await page.evaluate(() => document.documentElement.dataset.theme);
  console.log(path, response?.status(), "data-theme:", theme);
}
console.log("problems:", problems);
await browser.close();
