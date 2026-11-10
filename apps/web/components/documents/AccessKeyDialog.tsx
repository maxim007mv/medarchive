"use client";

import { Copy, Download } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { t, texts } from "@/lib/texts";

import { todayIso } from "./EditForm";

function downloadKey(accessKey: string): void {
  const blob = new Blob([t("accessKey.file.body", { key: accessKey })], {
    type: "text/plain;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = t("accessKey.file.name", { "YYYY-MM-DD": todayIso() });
  link.click();
  URL.revokeObjectURL(url);
}

/**
 * The access key right after it was issued (TC-004, FE-22). The server keeps only its hash,
 * so this is the one time it can be shown.
 */
export function AccessKeyDialog({
  accessKey,
  onClose,
}: {
  accessKey: string;
  onClose: () => void;
}) {
  const showToast = useToast();

  async function copy() {
    try {
      await navigator.clipboard.writeText(accessKey);
      showToast({ title: texts["accessKey.copied"] });
    } catch {
      // Clipboard denied: the key stays on screen with select-all, so it can still be copied by hand.
    }
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={texts["accessKey.title"]}
      description={texts["accessKey.text"]}
      footer={
        <Button onClick={onClose} className="md:min-w-24">
          {texts["accessKey.done"]}
        </Button>
      }
    >
      <Alert variant="warn" title={texts["accessKey.once"]} />
      <p
        data-testid="access-key"
        className="bg-sunken text-h3 rounded-lg px-4 py-3 text-center font-mono tracking-wide break-all select-all"
      >
        {accessKey}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" icon={Copy} onClick={() => void copy()}>
          {texts["accessKey.copy"]}
        </Button>
        <Button variant="secondary" icon={Download} onClick={() => downloadKey(accessKey)}>
          {texts["accessKey.download"]}
        </Button>
      </div>
    </Dialog>
  );
}
