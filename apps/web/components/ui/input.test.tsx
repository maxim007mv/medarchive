import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";

import { errorTitles, t, texts } from "@/lib/texts";

import { seriousViolations } from "./axe";
import { Input } from "./input";
import { Textarea } from "./textarea";

test("FE-04: label above, hint below and linked as the description", () => {
  render(<Input label={texts["upload.name.label"]} hint={texts["upload.name.hint"]} />);

  const input = screen.getByRole("textbox", { name: texts["upload.name.label"] });
  expect(input).toHaveAccessibleDescription(texts["upload.name.hint"]);
  expect(input).not.toHaveAttribute("aria-invalid");
});

test("FE-04: an error replaces the hint, is announced and marks the field invalid", () => {
  render(
    <Input
      label={texts["upload.name.label"]}
      hint={texts["upload.name.hint"]}
      error={errorTitles.title_required}
    />,
  );

  const input = screen.getByRole("textbox", { name: texts["upload.name.label"] });
  expect(input).toHaveAttribute("aria-invalid", "true");
  expect(input).toHaveAccessibleDescription(errorTitles.title_required);
  expect(screen.getByRole("alert")).toHaveTextContent(errorTitles.title_required);
  expect(screen.queryByText(texts["upload.name.hint"])).not.toBeInTheDocument();
});

test("FE-04: Textarea counts typed characters, also when uncontrolled", async () => {
  render(
    <Textarea
      label={texts["note.label"]}
      placeholder={texts["note.placeholder"]}
      counter={(n) => t("note.counter", { n })}
    />,
  );
  const textarea = screen.getByRole("textbox", { name: texts["note.label"] });

  await userEvent.type(textarea, "ЭКГ");

  expect(textarea).toHaveAccessibleDescription(t("note.counter", { n: 3 }));
});

test("FE-04: fields have no serious axe violations", async () => {
  const { container } = render(
    <div>
      <Input
        label={texts["search.placeholder"]}
        labelHidden
        placeholder={texts["search.placeholder"]}
      />
      <Input label={texts["upload.name.label"]} error={errorTitles.title_required} />
      <Input label={texts["upload.name.label"]} disabled defaultValue="ЭКГ покоя" />
      <Textarea label={texts["note.label"]} counter={(n) => t("note.counter", { n })} />
    </div>,
  );

  expect(await seriousViolations(container)).toEqual([]);
});
