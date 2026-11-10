import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Download, Eye } from "lucide-react";
import { expect, test, vi } from "vitest";

import { texts } from "@/lib/texts";

import { seriousViolations } from "./axe";
import { IconButton } from "./icon-button";

test("FE-08: the label is the accessible name and the hover tooltip", async () => {
  render(<IconButton icon={Eye} aria-label={texts["list.row.open"]} />);
  const button = screen.getByRole("button", { name: texts["list.row.open"] });

  await userEvent.tab();
  expect(button).toHaveFocus();
  expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  await userEvent.hover(button);

  expect(await screen.findByRole("tooltip")).toHaveTextContent(texts["list.row.open"]);
});

test("FE-08: disabled keeps focus, blocks clicks and explains why", async () => {
  const onClick = vi.fn();
  render(
    <IconButton
      icon={Download}
      aria-label={texts["header.export"]}
      disabled
      disabledReason={texts["export.emptyArchive"]}
      onClick={onClick}
    />,
  );
  const button = screen.getByRole("button", { name: texts["header.export"] });

  await userEvent.click(button);

  expect(onClick).not.toHaveBeenCalled();
  expect(button).toHaveAttribute("aria-disabled", "true");
  expect(button).toHaveAccessibleDescription(texts["export.emptyArchive"]);
});

test("FE-08: both sizes have no serious axe violations", async () => {
  const { container } = render(
    <div>
      <IconButton icon={Eye} aria-label={texts["list.row.open"]} />
      <IconButton icon={Eye} aria-label={texts["list.row.open"]} size="sm" variant="outline" />
    </div>,
  );

  expect(await seriousViolations(container)).toEqual([]);
});

export function IconButtonWithoutLabel() {
  // @ts-expect-error FE-08: an icon button without aria-label must not compile.
  return <IconButton icon={Eye} />;
}
