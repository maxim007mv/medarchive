import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useRef, useState } from "react";
import { expect, test, vi } from "vitest";

import { t, texts } from "@/lib/texts";

import { seriousViolations } from "./axe";
import { Button } from "./button";
import { Dialog, DialogClose } from "./dialog";
import { Input } from "./input";

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

test("FE-06: a form dialog starts on its first field, not on the cross", async () => {
  render(
    <Dialog open onOpenChange={() => undefined} title={texts["upload.title"]}>
      <Input label={texts["upload.name.label"]} />
    </Dialog>,
  );

  expect(await screen.findByRole("textbox", { name: texts["upload.name.label"] })).toHaveFocus();
});

function HandOff({ withOpener = true }: { withOpener?: boolean }) {
  const [step, setStep] = useState<"none" | "first" | "second">("none");
  const [showOpener, setShowOpener] = useState(true);
  const fallbackRef = useRef<HTMLHeadingElement>(null);
  return (
    <>
      <h1 ref={fallbackRef} tabIndex={-1}>
        {texts["list.title"]}
      </h1>
      {showOpener && <Button onClick={() => setStep("first")}>{texts["header.add"]}</Button>}
      <Dialog
        open={step === "first"}
        onOpenChange={() => setStep("none")}
        title={texts["upload.title"]}
        footer={
          <Button
            onClick={() => {
              setStep("second");
              if (!withOpener) setShowOpener(false);
            }}
          >
            {texts["upload.save"]}
          </Button>
        }
      />
      <Dialog
        open={step === "second"}
        onOpenChange={() => setStep("none")}
        handOff
        finalFocus={fallbackRef}
        title={texts["accessKey.title"]}
        footer={<Button onClick={() => setStep("none")}>{texts["accessKey.done"]}</Button>}
      />
    </>
  );
}

const nextTask = () => new Promise((resolve) => setTimeout(resolve, 0));

test("FE-06: a hand-off dialog replaces the closing one under a still scrim and keeps focus", async () => {
  render(<HandOff />);
  const opener = screen.getByRole("button", { name: texts["header.add"] });
  await userEvent.click(opener);
  expect(screen.getByRole("dialog").parentElement?.className).toContain("animate-fade-in");

  await userEvent.click(screen.getByRole("button", { name: texts["upload.save"] }));
  await nextTask();

  const dialogs = screen.getAllByRole("dialog");
  expect(dialogs).toHaveLength(1);
  expect(dialogs[0]).toHaveAccessibleName(texts["accessKey.title"]);
  expect(dialogs[0]?.parentElement?.className).not.toContain("animate-fade-in");
  expect(screen.getByRole("button", { name: texts["accessKey.done"] })).toHaveFocus();

  await userEvent.click(screen.getByRole("button", { name: texts["accessKey.done"] }));
  await nextTask();

  expect(opener).toHaveFocus();
});

test("FE-06: when the opener is gone, focus goes to finalFocus instead of the page body", async () => {
  render(<HandOff withOpener={false} />);
  await userEvent.click(screen.getByRole("button", { name: texts["header.add"] }));
  await userEvent.click(screen.getByRole("button", { name: texts["upload.save"] }));
  await nextTask();
  expect(screen.queryByRole("button", { name: texts["header.add"] })).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: texts["accessKey.done"] }));
  await nextTask();

  expect(screen.getByRole("heading", { name: texts["list.title"] })).toHaveFocus();
});

test("FE-06: unmounting on close still returns focus to the opener", async () => {
  function UnmountOnClose() {
    const [open, setOpen] = useState(false);
    return (
      <>
        <Button onClick={() => setOpen(true)}>{texts["header.export"]}</Button>
        {open && (
          <Dialog open onOpenChange={(next) => !next && setOpen(false)} title={texts["export.title"]}>
            <Button onClick={() => setOpen(false)}>{texts["common.cancel"]}</Button>
          </Dialog>
        )}
      </>
    );
  }

  render(<UnmountOnClose />);
  const opener = screen.getByRole("button", { name: texts["header.export"] });
  await userEvent.click(opener);
  await userEvent.click(screen.getByRole("button", { name: texts["common.cancel"] }));
  await nextTask();

  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(opener).toHaveFocus();
});
