import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { expect, test } from "vitest";

import { plural } from "@/lib/format";
import { plurals, t, texts } from "@/lib/texts";

import { seriousViolations } from "./axe";
import { Checkbox } from "./checkbox";
import { RadioRow, RadioRowGroup } from "./radio-row";
import { SegmentedControl } from "./segmented-control";

type DocumentType = "analysis" | "conclusion" | "other";
const typeOptions = [
  { value: "analysis", label: texts["type.analysis"] },
  { value: "conclusion", label: texts["type.conclusion"] },
  { value: "other", label: texts["type.other"] },
] as const;

function TypeSegment({ initial }: { initial?: DocumentType }) {
  const [value, setValue] = useState<DocumentType | undefined>(initial);
  return (
    <SegmentedControl
      label={texts["upload.type.label"]}
      options={typeOptions}
      value={value}
      onValueChange={setValue}
      fullWidth
    />
  );
}

function ExportScope() {
  const [scope, setScope] = useState<"filtered" | "all" | "selected">("filtered");
  const documents = (n: number) =>
    t("export.all.count", { n, документ: plural(n, plurals.документ) });
  return (
    <RadioRowGroup aria-label={texts["export.title"]} value={scope} onValueChange={setScope}>
      <RadioRow value="filtered" title={texts["export.filtered"]} description={documents(3)} />
      <RadioRow value="all" title={texts["export.all"]} description={documents(6)} />
      <RadioRow
        value="selected"
        title={texts["export.selected"]}
        description={texts["export.selected.none"]}
        disabled
      />
    </RadioRowGroup>
  );
}

/** Radix moves focus in a timeout and selects only while the arrow is still down. */
async function pressArrowRight(expectFocusOn: HTMLElement) {
  await userEvent.keyboard("{ArrowRight>}");
  await waitFor(() => expect(expectFocusOn).toHaveFocus());
  await userEvent.keyboard("{/ArrowRight}");
}

test("FE-05: arrow keys move through the segments and select them", async () => {
  render(<TypeSegment initial="analysis" />);
  expect(screen.getByRole("radiogroup", { name: texts["upload.type.label"] })).toBeInTheDocument();
  const radio = (name: string) => screen.getByRole("radio", { name });

  await userEvent.tab();
  expect(radio(texts["type.analysis"])).toHaveFocus();
  await pressArrowRight(radio(texts["type.conclusion"]));

  expect(radio(texts["type.conclusion"])).toBeChecked();
  await pressArrowRight(radio(texts["type.other"]));
  await pressArrowRight(radio(texts["type.analysis"]));
  expect(radio(texts["type.analysis"])).toBeChecked();
});

test("FE-05: a segment can start with nothing selected", () => {
  render(<TypeSegment />);

  expect(
    screen.getAllByRole("radio").filter((radio) => radio.getAttribute("aria-checked") === "true"),
  ).toEqual([]);
});

test("FE-05: a click on the row text selects the radio row", async () => {
  render(<ExportScope />);

  await userEvent.click(screen.getByText(texts["export.all"]));

  const all = screen.getByRole("radio", { name: texts["export.all"] });
  expect(all).toBeChecked();
  expect(all).toHaveAccessibleDescription("6 документов");
  await userEvent.click(screen.getByText(texts["export.selected.none"]));
  expect(screen.getByRole("radio", { name: texts["export.selected"] })).not.toBeChecked();
  expect(all).toBeChecked();
});

test("FE-05: a click on the checkbox label toggles it", async () => {
  render(<Checkbox label={texts["upload.date.none"]} />);

  await userEvent.click(screen.getByText(texts["upload.date.none"]));

  expect(screen.getByRole("checkbox", { name: texts["upload.date.none"] })).toBeChecked();
});

test("FE-05: a checkbox without visible text is named by aria-label and can be mixed", () => {
  render(<Checkbox aria-label={texts["list.selectAll"]} checked="indeterminate" />);

  expect(screen.getByRole("checkbox", { name: texts["list.selectAll"] })).toBePartiallyChecked();
});

test("FE-05: choice controls have no serious axe violations", async () => {
  const { container } = render(
    <div>
      <TypeSegment initial="other" />
      <ExportScope />
      <Checkbox label={texts["upload.date.none"]} defaultChecked />
      <Checkbox aria-label={texts["list.selectAll"]} disabled />
    </div>,
  );

  expect(await seriousViolations(container)).toEqual([]);
});
