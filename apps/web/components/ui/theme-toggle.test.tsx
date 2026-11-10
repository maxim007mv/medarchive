import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test } from "vitest";

import { texts } from "@/lib/texts";

import { THEME_STORAGE_KEY } from "./theme";
import { ThemeToggle } from "./theme-toggle";

beforeEach(() => {
  localStorage.clear();
  document.documentElement.dataset.theme = "light";
});

test("FE-01: the header switch flips the theme and saves the choice", async () => {
  render(<ThemeToggle />);

  await userEvent.click(screen.getByRole("button", { name: texts["header.theme.dark"] }));

  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
  expect(await screen.findByRole("button", { name: texts["header.theme.light"] })).toBeVisible();
});
