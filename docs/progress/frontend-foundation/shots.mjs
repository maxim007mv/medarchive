import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
// Playwright comes from the e2e package; run from the repo root with the gallery dev server up:
// GALLERY_URL=http://localhost:3300/ui node docs/progress/frontend-foundation/shots.mjs
const require = createRequire(new URL("../../../e2e/package.json", import.meta.url));
const { chromium } = require("@playwright/test");

const OUT = fileURLToPath(new URL(".", import.meta.url));
const GALLERY_URL = process.env.GALLERY_URL ?? "http://localhost:3300/ui";
const browser = await chromium.launch();
const report = {};

async function open(theme, viewport) {
  const context = await browser.newContext({ viewport, locale: "ru-RU", timezoneId: "Europe/Moscow", colorScheme: theme, reducedMotion: "reduce" });
  const page = await context.newPage();
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(GALLERY_URL, { waitUntil: "networkidle", timeout: 120000 });
  await page.evaluate(() => document.fonts.ready);
  return { context, page, errors };
}

async function closeDialog(page) {
  for (let presses = 1; presses <= 4; presses += 1) {
    await page.keyboard.press("Escape");
    if ((await page.getByRole("dialog").count()) === 0) return presses;
  }
  throw new Error("dialog did not close");
}

for (const theme of ["light", "dark"]) {
  const { context, page, errors } = await open(theme, { width: 1440, height: 900 });
  report[`${theme}.dataTheme`] = await page.evaluate(() => document.documentElement.dataset.theme);
  await page.screenshot({ path: `${OUT}/gallery-${theme}.png`, fullPage: true });

  await page.getByRole("button", { name: "Новый документ" }).click();
  await page.getByRole("dialog").waitFor();
  await page.screenshot({ path: `${OUT}/dialog-form-${theme}.png` });
  await page.getByRole("button", { name: "Открыть календарь" }).last().focus();
  await page.keyboard.press("Enter");
  await page.getByRole("table").waitFor();
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${OUT}/date-popover-${theme}.png` });
  report[`${theme}.escapesToClose`] = await closeDialog(page);

  await page.getByRole("button", { name: "Удалить документ" }).click();
  await page.getByRole("dialog").waitFor();
  report[`${theme}.deleteFocus`] = await page.evaluate(() => document.activeElement?.textContent);
  await page.screenshot({ path: `${OUT}/dialog-delete-${theme}.png` });
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: "Открыть", exact: true }).first().click();
  await page.getByRole("region").getByText("добавлен").waitFor();
  await page.screenshot({ path: `${OUT}/toast-${theme}.png` });

  report[`${theme}.consoleErrors`] = errors;
  await context.close();
}

{
  const { context, page, errors } = await open("light", { width: 390, height: 844 });
  await page.getByRole("button", { name: "Новый документ" }).click();
  await page.getByRole("dialog").waitFor();
  await page.screenshot({ path: `${OUT}/sheet-form-mobile-light.png` });
  report["mobile.escapesToClose"] = await closeDialog(page);
  await page.getByRole("button", { name: "Удалить документ" }).click();
  await page.getByRole("dialog").waitFor();
  await page.screenshot({ path: `${OUT}/sheet-delete-mobile-light.png` });
  const box = await page.getByRole("button", { name: "Удалить", exact: true }).boundingBox();
  report["mobile.deleteButtonHeight"] = box?.height;
  report["mobile.consoleErrors"] = errors;
  await context.close();
}

{
  // Button width with and without loading, measured in the real layout.
  const { context, page } = await open("light", { width: 1440, height: 900 });
  report.buttonWidths = await page.evaluate(() => {
    const buttons = [...document.querySelectorAll("button")].filter((b) => /Сохранить в архив|Сохраняем/.test(b.textContent ?? ""));
    return buttons.slice(0, 3).map((b) => ({ text: b.innerText, width: b.getBoundingClientRect().width, busy: b.getAttribute("aria-busy") }));
  });
  report.renderedFont = await page.evaluate(() => getComputedStyle(document.body).fontFamily);
  report.fontsLoaded = await page.evaluate(() => [...document.fonts].filter((f) => f.status === "loaded").map((f) => f.family));
  await context.close();
}

await browser.close();
console.log(JSON.stringify(report, null, 2));
