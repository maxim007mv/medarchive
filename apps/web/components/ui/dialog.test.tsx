import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useRef, useState } from "react";
import { expect, test, vi } from "vitest";

import { t, texts } from "@/lib/texts";

import { seriousViolations } from "./axe";
import { Button } from "./button";
import { Dialog, DialogClose } from "./dialog";

function DeleteConfirm({ onDelete }: { onDelete: () => void }) {
  const [open, setOpen] = useState(false);
  const cancelRef = useRef<HTMLButtonElement>(null);
  return (
    <>
      <Button variant="dangerText" onClick={() => setOpen(true)}>
        {texts["doc.delete"]}
      </Button>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title={texts["delete.title"]}
        description={t("delete.text", { title: "Заключение терапевта", date: "10.04.2026" })}
        width="confirm"
        initialFocus={cancelRef}
        footer={
          <>
            <DialogClose asChild>
              <Button ref={cancelRef} variant="secondary">
                {texts["delete.cancel"]}
              </Button>
            </DialogClose>
            <Button variant="danger" onClick={onDelete}>
              {texts["delete.confirm"]}
            </Button>
          </>
        }
      />
    </>
  );
}

test("FE-06: Esc closes the dialog and focus returns to the button that opened it", async () => {
  render(<DeleteConfirm onDelete={vi.fn()} />);
  const opener = screen.getByRole("button", { name: texts["doc.delete"] });

  await userEvent.click(opener);
  expect(screen.getByRole("dialog", { name: texts["delete.title"] })).toBeInTheDocument();
  await userEvent.keyboard("{Escape}");

  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(opener).toHaveFocus();
});

test("FE-06: a delete confirmation focuses «Отмена» and Enter does not delete", async () => {
  const onDelete = vi.fn();
  render(<DeleteConfirm onDelete={onDelete} />);

  await userEvent.click(screen.getByRole("button", { name: texts["doc.delete"] }));
  const dialog = screen.getByRole("dialog", { name: texts["delete.title"] });
  expect(screen.getByRole("button", { name: texts["delete.cancel"] })).toHaveFocus();
  expect(dialog).toHaveAccessibleDescription(
    t("delete.text", { title: "Заключение терапевта", date: "10.04.2026" }),
  );
  await userEvent.keyboard("{Enter}");

  expect(onDelete).not.toHaveBeenCalled();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

test("FE-06: focus is trapped inside the dialog", async () => {
  render(<DeleteConfirm onDelete={vi.fn()} />);
  await userEvent.click(screen.getByRole("button", { name: texts["doc.delete"] }));
  const dialog = screen.getByRole("dialog");

  for (let i = 0; i < 4; i += 1) {
    await userEvent.tab();
    expect(dialog).toContainElement(document.activeElement as HTMLElement);
  }
});

test("FE-06: the cross is named and the dialog has no serious axe violations", async () => {
  render(<DeleteConfirm onDelete={vi.fn()} />);
  await userEvent.click(screen.getByRole("button", { name: texts["doc.delete"] }));

  expect(screen.getByRole("button", { name: texts["common.close"] })).toBeInTheDocument();
  expect(await seriousViolations(document.body)).toEqual([]);
});
