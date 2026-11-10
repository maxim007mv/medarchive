import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Plus } from "lucide-react";
import { expect, test, vi } from "vitest";

import { texts } from "@/lib/texts";

import { seriousViolations } from "./axe";
import { Button } from "./button";

test("FE-03: loading keeps the idle label in the same grid cell, so the width does not change", () => {
  const { rerender } = render(
    <Button loadingText={texts["upload.saving"]}>{texts["upload.save"]}</Button>,
  );
  const button = screen.getByRole("button", { name: texts["upload.save"] });
  const [idle, busy] = button.children;
  expect(idle).not.toHaveClass("invisible");
  expect(busy).toHaveClass("invisible");

  rerender(
    <Button loading loadingText={texts["upload.saving"]}>
      {texts["upload.save"]}
    </Button>,
  );

  expect(button).toHaveAccessibleName(texts["upload.saving"]);
  expect(button).toHaveAttribute("aria-busy", "true");
  expect(button).toHaveAttribute("aria-disabled", "true");
  // Both layers stay rendered in one cell: the button is as wide as the wider of the two.
  expect(button.children).toHaveLength(2);
  expect(idle).toHaveClass("invisible", "col-start-1", "row-start-1");
  expect(busy).toHaveClass("col-start-1", "row-start-1");
  expect(busy).not.toHaveClass("invisible");
  expect(idle).toHaveTextContent(texts["upload.save"]);
});

test("FE-03: a loading button ignores clicks", async () => {
  const onClick = vi.fn();
  render(
    <Button loading onClick={onClick}>
      {texts["upload.save"]}
    </Button>,
  );

  await userEvent.click(screen.getByRole("button"));

  expect(onClick).not.toHaveBeenCalled();
});

test("FE-03: disabled uses aria-disabled, stays focusable and announces the reason", async () => {
  const onClick = vi.fn();
  render(
    <Button disabled disabledReason={texts["upload.save.disabledReason"]} onClick={onClick}>
      {texts["upload.save"]}
    </Button>,
  );
  const button = screen.getByRole("button", { name: texts["upload.save"] });

  await userEvent.tab();
  await userEvent.click(button);

  expect(button).toHaveFocus();
  expect(button).not.toHaveAttribute("disabled");
  expect(button).toHaveAttribute("aria-disabled", "true");
  expect(button).toHaveAccessibleDescription(texts["upload.save.disabledReason"]);
  expect(onClick).not.toHaveBeenCalled();
});

test("FE-03: a disabled submit button does not submit the form", async () => {
  const onSubmit = vi.fn((event: SubmitEvent) => event.preventDefault());
  render(
    <form onSubmit={(event) => onSubmit(event.nativeEvent as SubmitEvent)}>
      <input aria-label={texts["upload.name.label"]} />
      <Button type="submit" disabled>
        {texts["upload.save"]}
      </Button>
    </form>,
  );

  await userEvent.type(screen.getByRole("textbox"), "x{Enter}");
  await userEvent.click(screen.getByRole("button"));

  expect(onSubmit).not.toHaveBeenCalled();
});

test("FE-03: variants and sizes have no serious axe violations", async () => {
  const { container } = render(
    <div>
      {(["primary", "secondary", "tertiary", "danger", "dangerText"] as const).map((variant) =>
        (["sm", "md", "lg"] as const).map((size) => (
          <Button key={variant + size} variant={variant} size={size} icon={Plus}>
            {texts["header.add"]}
          </Button>
        )),
      )}
      <Button disabled disabledReason={texts["export.emptyArchive"]}>
        {texts["header.export"]}
      </Button>
    </div>,
  );

  expect(await seriousViolations(container)).toEqual([]);
});
