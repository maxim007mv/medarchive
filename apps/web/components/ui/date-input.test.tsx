import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode, useState } from "react";
import { expect, test } from "vitest";

import { errorTitles, texts } from "@/lib/texts";
import { parseDate } from "@/lib/format";

import { DateInput } from "./date-input";
import { Dialog } from "./dialog";

function DateField({ initial = "", max }: { initial?: string; max?: string }) {
  const [value, setValue] = useState(initial);
  const isInvalid = value.length === 10 && parseDate(value) === null;
  return (
    <DateInput
      label={texts["upload.date.label"]}
      value={value}
      onChange={setValue}
      max={max}
      error={isInvalid ? errorTitles.date_invalid : undefined}
    />
  );
}

const field = () => screen.getByRole("textbox", { name: texts["upload.date.label"] });

test("FE-04: 31.02.2026 is typed through the mask and is not a date", async () => {
  render(<DateField />);

  await userEvent.type(field(), "31022026");

  expect(field()).toHaveValue("31.02.2026");
  expect(field()).toHaveAttribute("aria-invalid", "true");
  expect(field()).toHaveAccessibleDescription(errorTitles.date_invalid);
});

test("FE-04: 29.02.2028 is a valid leap day and the calendar opens on it", async () => {
  render(<DateField />);

  await userEvent.type(field(), "29.02.2028");
  await userEvent.click(screen.getByRole("button", { name: texts["upload.date.calendar"] }));

  expect(field()).toHaveValue("29.02.2028");
  expect(field()).not.toHaveAttribute("aria-invalid");
  const day = await screen.findByRole("button", { name: "29 февраля 2028 г." });
  expect(day).toHaveAttribute("aria-pressed", "true");
  expect(day).toHaveFocus();
});

test("FE-04: the calendar is driven by the keyboard and returns focus to the date field", async () => {
  render(<DateField initial="08.04.2026" />);
  const calendarButton = screen.getByRole("button", { name: texts["upload.date.calendar"] });

  calendarButton.focus();
  await userEvent.keyboard("{Enter}");
  expect(await screen.findByRole("button", { name: "8 апреля 2026 г." })).toHaveFocus();
  await userEvent.keyboard("{ArrowRight}{ArrowDown}{Enter}");

  expect(field()).toHaveValue("16.04.2026");
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(field()).toHaveFocus();
});

test("FE-04: days after max are not offered", async () => {
  render(<DateField initial="10.11.2026" max="2026-11-10" />);

  await userEvent.click(screen.getByRole("button", { name: texts["upload.date.calendar"] }));

  expect(await screen.findByRole("button", { name: "10 ноября 2026 г." })).toBeEnabled();
  expect(screen.getByRole("button", { name: "11 ноября 2026 г." })).toBeDisabled();
});

test("FE-04: a disabled date field shows «Не указана» and opens no calendar", async () => {
  render(
    <DateInput
      label={texts["upload.date.label"]}
      value={texts["upload.date.noneValue"]}
      onChange={() => undefined}
      disabled
    />,
  );

  await userEvent.click(screen.getByRole("button", { name: texts["upload.date.calendar"] }));

  expect(field()).toBeDisabled();
  expect(field()).toHaveValue(texts["upload.date.noneValue"]);
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

test("FE-04: inside a dialog, Esc closes the calendar first and the dialog next", async () => {
  function DialogWithDate() {
    const [open, setOpen] = useState(true);
    const [value, setValue] = useState("");
    return (
      <Dialog open={open} onOpenChange={setOpen} title={texts["upload.title"]}>
        <DateInput label={texts["upload.date.label"]} value={value} onChange={setValue} />
      </Dialog>
    );
  }
  render(
    <StrictMode>
      <DialogWithDate />
    </StrictMode>,
  );

  screen.getByRole("button", { name: texts["upload.date.calendar"] }).focus();
  await userEvent.keyboard("{Enter}");
  expect(await screen.findByRole("table")).toBeInTheDocument();
  await userEvent.keyboard("{Escape}");

  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(field()).toHaveFocus();
  await userEvent.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
