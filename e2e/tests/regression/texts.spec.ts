import type { Page } from "@playwright/test";

import { expect, test } from "../../support/fixtures";

// QA-07, step 6 of the manual checklist automated: rules of docs/texts.md, section 1 and 2, on
// what the user actually sees. Latin is allowed for file formats and the file-name example.
const ALLOWED_LATIN = new Set(["PDF", "ZIP", "CSV", "JSON", "Excel", "Medeo"]);
const FILE_NAME = /[\w-]+\.(pdf|csv|json|zip)\b/gi;

async function visibleText(page: Page): Promise<string> {
  return page.locator("body").innerText();
}

function textRuleViolations(text: string): string[] {
  const withoutFileNames = text.replace(FILE_NAME, "");
  const latin = (withoutFileNames.match(/\b[A-Za-z]{2,}\b/g) ?? []).filter((word) => !ALLOWED_LATIN.has(word));
  const violations = [...new Set(latin)].map((word) => `latin word «${word}»`);
  if (text.includes("\u2014")) violations.push("em dash U+2014");
  if (text.includes("...")) violations.push("three dots instead of U+2026");
  for (const date of withoutFileNames.match(/\b\d{4}-\d{2}-\d{2}\b/g) ?? []) violations.push(`ISO date ${date}`);
  for (const date of text.match(/\b\d{1,2}\.\d{1,2}\.\d{2,4}\b/g) ?? []) {
    if (!/^\d{2}\.\d{2}\.\d{4}$/.test(date)) violations.push(`date ${date} is not дд.мм.гггг`);
  }
  return violations;
}

test("QA-07 onboarding and policy texts follow docs/texts.md", { tag: ["@b3", "@regression"] }, async ({ page }) => {
  for (const path of ["/", "/policy"]) {
    await page.goto(path);
    expect(textRuleViolations(await visibleText(page)), path).toEqual([]);
  }
});

test("QA-07 archive list texts follow docs/texts.md", { tag: ["@b5", "@regression"] }, async ({ page, freshArchive }) => {
  await freshArchive.api.addAllSources();

  await page.goto("/");
  await expect(page.getByText("Общий анализ крови").first()).toBeVisible();

  expect(textRuleViolations(await visibleText(page))).toEqual([]);
});
