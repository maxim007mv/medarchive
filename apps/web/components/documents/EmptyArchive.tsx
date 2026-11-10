"use client";

import { Plus, ShieldCheck, Upload } from "lucide-react";
import Link from "next/link";
import { useId, useRef, useState, type DragEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/components/ui/cn";
import { PDF_MIME } from "@/lib/api/upload";
import { texts } from "@/lib/texts";

const STEPS = [
  {
    title: "onboarding.step1.title",
    text: "onboarding.step1.text",
    mobileText: "onboarding.step1.text.mobile",
  },
  {
    title: "onboarding.step2.title",
    text: "onboarding.step2.text",
    mobileText: "onboarding.step2.text.mobile",
  },
  {
    title: "onboarding.step3.title",
    text: "onboarding.step3.text",
    mobileText: "onboarding.step3.text.mobile",
  },
] as const;

type Props = {
  /** No archive yet: the files can be chosen only after the consent (FE-11, 152-ФЗ ст. 10). */
  needsConsent: boolean;
  onFiles: (files: File[]) => void;
  busy: boolean;
  /** Catalogue text of a rejected first file or of a failed archive creation. */
  error?: string;
  disabledReason?: string;
};

/** D01 / M01: empty archive that teaches the next step instead of an empty table. */
export function EmptyArchive({ needsConsent, onFiles, busy, error, disabledReason }: Props) {
  const [consent, setConsent] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const pickerRef = useRef<HTMLInputElement>(null);
  const reasonId = useId();
  const reason =
    disabledReason ??
    (needsConsent && !consent ? texts["onboarding.pick.disabledReason"] : undefined);
  const locked = Boolean(reason);

  function drop(event: DragEvent) {
    event.preventDefault();
    setDragOver(false);
    if (!locked && !busy) onFiles([...event.dataTransfer.files]);
  }

  return (
    <main className="mx-auto grid w-full max-w-6xl gap-8 px-4 py-8 lg:grid-cols-2 lg:gap-12 lg:px-6 lg:py-16">
      <div className="flex flex-col gap-6">
        <span className="bg-sunken text-caption text-text2 hidden self-start rounded-full px-2.5 py-1 lg:inline">
          {texts["onboarding.badge"]}
        </span>
        <h1 className="text-h1 lg:text-display">{texts["onboarding.title"]}</h1>
        <p className="text-body-l text-text2">
          <span className="hidden md:inline">{texts["onboarding.lead"]}</span>
          <span className="md:hidden">{texts["onboarding.lead.mobile"]}</span>
        </p>
        <ol className="flex flex-col gap-4">
          {STEPS.map((step, index) => (
            <li key={step.title} className="flex gap-3">
              <span
                className="bg-accent-soft text-caption text-accent grid size-6 shrink-0 place-items-center rounded-full font-medium"
                aria-hidden
              >
                {index + 1}
              </span>
              <div className="flex flex-col gap-0.5">
                <p className="text-label">{texts[step.title]}</p>
                <p className="text-caption text-text2">
                  <span className="hidden md:inline">{texts[step.text]}</span>
                  <span className="md:hidden">{texts[step.mobileText]}</span>
                </p>
              </div>
            </li>
          ))}
        </ol>
        <section className="bg-sunken flex gap-3 rounded-lg p-4">
          <ShieldCheck
            size={16}
            strokeWidth={1.75}
            className="text-text2 mt-0.5 shrink-0"
            aria-hidden
          />
          <div className="flex flex-col gap-1">
            <h2 className="text-label">{texts["onboarding.storage.title"]}</h2>
            <p className="text-caption text-text2">
              <span className="hidden md:inline">{texts["onboarding.storage.text"]}</span>
              <span className="md:hidden">{texts["onboarding.storage.text.mobile"]}</span>
            </p>
          </div>
        </section>
      </div>

      <section
        aria-labelledby="drop-title"
        onDragOver={(event) => {
          event.preventDefault();
          if (!locked) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={drop}
        className={cn(
          "duration-fast flex flex-col items-center justify-center gap-4 self-start rounded-2xl border border-dashed p-8 text-center transition-colors",
          dragOver ? "border-accent bg-accent-soft" : "border-control bg-surface",
        )}
      >
        <span
          className="bg-accent-soft text-accent grid size-12 place-items-center rounded-xl"
          aria-hidden
        >
          <Upload size={20} strokeWidth={1.75} />
        </span>
        <div className="flex flex-col gap-2">
          <h2 id="drop-title" className="text-h3">
            {dragOver ? texts["upload.dropOver"] : texts["onboarding.drop.title"]}
          </h2>
          <p className="text-caption text-text2 hidden md:block">{texts["onboarding.drop.text"]}</p>
        </div>
        {needsConsent && (
          <div className="flex max-w-sm flex-col gap-1.5 text-left">
            <Checkbox
              label={
                <span className="text-label font-normal">{texts["onboarding.consent.label"]}</span>
              }
              checked={consent}
              onCheckedChange={(checked) => setConsent(checked === true)}
              className="items-start"
            />
            <Link
              href="/policy"
              className="text-caption text-accent self-start rounded-xs underline"
            >
              {texts["onboarding.consent.policyLink"]}
            </Link>
          </div>
        )}
        <Button
          size="lg"
          icon={Plus}
          loading={busy}
          disabled={locked}
          aria-describedby={reason ? reasonId : undefined}
          onClick={() => pickerRef.current?.click()}
        >
          {texts["onboarding.pick"]}
        </Button>
        {reason && (
          <p id={reasonId} className="text-caption text-text3">
            {reason}
          </p>
        )}
        <input
          ref={pickerRef}
          type="file"
          accept={PDF_MIME}
          multiple
          hidden
          data-testid="onboarding-file-input"
          onChange={(event) => {
            onFiles([...(event.target.files ?? [])]);
            event.target.value = "";
          }}
        />
        {error && <Alert variant="danger" title={error} className="w-full text-left" />}
        <p className="text-caption text-text3">{texts["onboarding.drop.limits"]}</p>
        {needsConsent && (
          <Link href="/restore" className="text-caption text-accent rounded-xs underline">
            {texts["onboarding.restore"]}
          </Link>
        )}
      </section>
    </main>
  );
}
