import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { applyTheme, THEME_STORAGE_KEY, themeScript } from "./theme";

function mockSystemDark(isDark: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({ matches: isDark && query === "(prefers-color-scheme: dark)" })),
  );
}

function runThemeScript() {
  // The same string the layout inlines into <head>.
  new Function(themeScript)();
}

beforeEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("FE-01: without a saved choice the theme follows prefers-color-scheme", () => {
  mockSystemDark(true);
  runThemeScript();
  expect(document.documentElement.dataset.theme).toBe("dark");

  mockSystemDark(false);
  runThemeScript();
  expect(document.documentElement.dataset.theme).toBe("light");
});

test("FE-01: a saved choice wins over the system preference", () => {
  mockSystemDark(true);
  localStorage.setItem(THEME_STORAGE_KEY, "light");

  runThemeScript();

  expect(document.documentElement.dataset.theme).toBe("light");
});

test("FE-01: an unknown saved value falls back to the system preference", () => {
  mockSystemDark(true);
  localStorage.setItem(THEME_STORAGE_KEY, "sepia");

  runThemeScript();

  expect(document.documentElement.dataset.theme).toBe("dark");
});

test("FE-01: applyTheme sets the attribute and remembers the choice", () => {
  applyTheme("dark");

  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
});
