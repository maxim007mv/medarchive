import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test } from "vitest";

import { seriousViolations } from "@/components/ui/axe";
import { ToastProvider } from "@/components/ui/toast";
import { texts } from "@/lib/texts";

import { Gallery } from "./gallery";

beforeEach(() => {
  // Set by the inline theme script in a real page.
  document.documentElement.dataset.theme = "light";
});

function renderGallery() {
  return render(
    <ToastProvider>
      <Gallery />
    </ToastProvider>,
  );
}

test("FE-01..FE-09: the component gallery has no serious axe violations", async () => {
  renderGallery();

  expect(await seriousViolations(document.body)).toEqual([]);
});

test("FE-06: the gallery dialogs open without serious axe violations", async () => {
  renderGallery();

  await userEvent.click(screen.getByRole("button", { name: texts["upload.title"] }));

  expect(screen.getByRole("dialog", { name: texts["upload.title"] })).toBeInTheDocument();
  expect(await seriousViolations(document.body)).toEqual([]);
});
