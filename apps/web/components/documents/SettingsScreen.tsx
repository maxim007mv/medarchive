"use client";

import { useQueryClient } from "@tanstack/react-query";
import { KeyRound, LogOut, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { Alert } from "@/components/ui/alert";
import { Button, buttonClasses } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { newIdempotencyKey } from "@/lib/api/client";
import {
  browserTimeZone,
  forgetArchive,
  useDeleteWorkspace,
  useLogout,
  useRotateKey,
  useSession,
  useWorkspace,
} from "@/lib/api/queries";
import { formatDateTime } from "@/lib/format";
import { t, texts } from "@/lib/texts";

import { AccessKeyDialog } from "./AccessKeyDialog";
import { AppHeader } from "./AppHeader";
import { BackLink } from "./BackLink";
import { OfflineBanner, useOfflineReason } from "./OfflineBanner";
import { useProblem } from "./use-problem";

/** The word to type, taken from the dictionary text that names it: «Введите слово «удалить»». */
const CONFIRM_WORD = /«(.+)»/.exec(texts["settings.danger.disabledReason"])?.[1] ?? "";

/** After trim, in any case: «удалить», «Удалить», «УДАЛИТЬ» (TC-084). */
export function isDeleteWordTyped(input: string): boolean {
  return (
    CONFIRM_WORD !== "" &&
    input.trim().toLocaleLowerCase("ru-RU") === CONFIRM_WORD.toLocaleLowerCase("ru-RU")
  );
}

function Section({
  title,
  children,
  danger,
}: {
  title: string;
  children: ReactNode;
  danger?: boolean;
}) {
  return (
    <section
      className={
        danger
          ? "border-danger bg-surface flex flex-col gap-4 rounded-xl border p-6"
          : "border-border bg-surface shadow-1 flex flex-col gap-4 rounded-xl border p-6"
      }
    >
      <h2 className={danger ? "text-h3 text-danger" : "text-h3"}>{title}</h2>
      {children}
    </section>
  );
}

/** «Хранение и доступ» (FE-22): where the data lives, the access key, logout and deleting the archive. */
export function SettingsScreen() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const session = useSession();
  // Warms the cache for the `If-Match` of «Удалить архив».
  useWorkspace({ enabled: Boolean(session.data) });
  const offlineReason = useOfflineReason();

  const rotate = useRotateKey();
  const [rotateKey, setRotateKey] = useState<string | null>(null);
  const [newKey, setNewKey] = useState<string | null>(null);
  const logout = useLogout();
  const deleteWorkspace = useDeleteWorkspace();
  const [word, setWord] = useState("");
  const [purgeBefore, setPurgeBefore] = useState<string | null>(null);
  const problem = useProblem(rotate.error ?? logout.error ?? deleteWorkspace.error);

  useEffect(() => {
    if (session.data === null && purgeBefore === null) router.replace("/");
  }, [session.data, purgeBefore, router]);

  if (purgeBefore) {
    const [date = "", time = ""] = formatDateTime(purgeBefore, browserTimeZone()).split(", ");
    return (
      <>
        <AppHeader />
        <main className="mx-auto flex max-w-lg flex-col gap-4 px-4 py-12">
          <BackLink className="-ml-3" />
          <h1 className="text-h1">{texts["settings.danger.title"]}</h1>
          <p role="status" className="text-body-l">
            {t("settings.danger.done", { date, time })}
          </p>
        </main>
      </>
    );
  }

  function confirmRotate() {
    if (!rotateKey) return;
    rotate.mutate(rotateKey, {
      onSuccess: (issued) => {
        setRotateKey(null);
        setNewKey(issued.access_key);
      },
    });
  }

  function removeArchive() {
    if (!isDeleteWordTyped(word)) return;
    deleteWorkspace.mutate(undefined, {
      onSuccess: (scheduled) => {
        setPurgeBefore(scheduled.purge_before);
        forgetArchive(queryClient);
      },
    });
  }

  const wordReason = isDeleteWordTyped(word) ? undefined : texts["settings.danger.disabledReason"];

  return (
    <>
      <AppHeader />
      <OfflineBanner />
      <main className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-4 py-8 lg:py-12">
        <BackLink className="-ml-3" />
        <h1 className="text-h1">{texts["settings.title"]}</h1>
        {problem && <Alert variant="danger" title={problem.title} />}

        <Section title={texts["settings.storage.title"]}>
          <p className="text-text2">{texts["settings.storage.text"]}</p>
        </Section>

        <Section title={texts["settings.key.title"]}>
          <p className="text-text2">{texts["accessKey.text"]}</p>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              icon={KeyRound}
              onClick={() => setRotateKey(newIdempotencyKey())}
              disabled={Boolean(offlineReason)}
              disabledReason={offlineReason}
            >
              {texts["settings.key.rotate"]}
            </Button>
            <Link href="/restore" className={buttonClasses({ variant: "tertiary" })}>
              {texts["restore.title"]}
            </Link>
          </div>
        </Section>

        <Button
          variant="secondary"
          icon={LogOut}
          loading={logout.isPending}
          onClick={() => logout.mutate(undefined, { onSuccess: () => router.push("/") })}
          className="self-start"
        >
          {texts["settings.logout"]}
        </Button>

        <Section title={texts["settings.danger.title"]} danger>
          <p className="text-text2">{texts["settings.danger.text"]}</p>
          <form
            noValidate
            onSubmit={(event) => {
              event.preventDefault();
              removeArchive();
            }}
            className="flex flex-col gap-4"
          >
            <Input
              label={texts["settings.danger.wordLabel"]}
              value={word}
              onChange={(event) => setWord(event.target.value)}
              autoComplete="off"
            />
            <Button
              type="submit"
              variant="danger"
              icon={Trash2}
              loading={deleteWorkspace.isPending}
              disabled={Boolean(offlineReason ?? wordReason)}
              disabledReason={offlineReason ?? wordReason}
              className="self-start"
            >
              {texts["settings.danger.submit"]}
            </Button>
          </form>
        </Section>
      </main>

      {rotateKey && (
        <Dialog
          open
          onOpenChange={(open) => !open && setRotateKey(null)}
          width="confirm"
          title={texts["settings.key.rotate.title"]}
          description={texts["settings.key.rotate.text"]}
          footer={
            <>
              <Button variant="secondary" onClick={() => setRotateKey(null)}>
                {texts["common.cancel"]}
              </Button>
              <Button loading={rotate.isPending} onClick={confirmRotate}>
                {texts["settings.key.rotate.confirm"]}
              </Button>
            </>
          }
        />
      )}
      {newKey && <AccessKeyDialog accessKey={newKey} onClose={() => setNewKey(null)} />}
    </>
  );
}
