"use client";

import {
  Download,
  Eye,
  MoreHorizontal,
  Plus,
  RotateCw,
  Search,
  Trash2,
  WifiOff,
} from "lucide-react";
import { useRef, useState, type ReactNode } from "react";

import { Alert } from "@/components/ui/alert";
import { Banner } from "@/components/ui/banner";
import { Button, type ButtonSize, type ButtonVariant } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Chip } from "@/components/ui/chip";
import { DateInput } from "@/components/ui/date-input";
import { Dialog, DialogClose } from "@/components/ui/dialog";
import { IconButton } from "@/components/ui/icon-button";
import { Input } from "@/components/ui/input";
import { RadioRow, RadioRowGroup } from "@/components/ui/radio-row";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { Skeleton } from "@/components/ui/skeleton";
import { TypeTag, UndatedTag, type DocumentType } from "@/components/ui/tag";
import { Textarea } from "@/components/ui/textarea";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { useToast } from "@/components/ui/toast";
import { formatSize, parseDate, plural } from "@/lib/format";
import { errorTitles, plurals, t, texts } from "@/lib/texts";

const VARIANTS: ButtonVariant[] = ["primary", "secondary", "tertiary", "danger", "dangerText"];
const SIZES: ButtonSize[] = ["sm", "md", "lg"];
const TYPE_OPTIONS = [
  { value: "analysis", label: texts["type.analysis"] },
  { value: "conclusion", label: texts["type.conclusion"] },
  { value: "other", label: texts["type.other"] },
] as const;
const DATE_FIELD_OPTIONS = [
  { value: "document", label: texts["filter.dateField.document"] },
  { value: "uploaded", label: texts["filter.dateField.uploaded"] },
] as const;
const SAMPLE_TITLE = "Заключение терапевта";
const documents = (n: number) => `${n} ${plural(n, plurals.документ)}`;

/** Dev-only catalogue of components/ui for visual snapshots in both themes. */
export function Gallery() {
  return (
    <main className="bg-bg text-text flex flex-col gap-6 p-8">
      <div className="flex items-center gap-4">
        <h1 className="text-h1">{texts["app.name"]} · components/ui</h1>
        <ThemeToggle />
      </div>
      <Overlays />
      <div className="grid gap-6 xl:grid-cols-2">
        <ThemePanel theme="light" />
        <ThemePanel theme="dark" />
      </div>
    </main>
  );
}

function ThemePanel({ theme }: { theme: "light" | "dark" }) {
  return (
    <div
      data-theme={theme}
      className="bg-bg text-text shadow-1 flex flex-col gap-8 rounded-2xl p-6"
    >
      <p className="text-h2">{theme}</p>
      <Section title="Button">
        <div className="grid grid-cols-3 items-center justify-items-start gap-3">
          {VARIANTS.map((variant) =>
            SIZES.map((size) => (
              <Button
                key={variant + size}
                variant={variant}
                size={size}
                icon={variant === "primary" ? Plus : undefined}
              >
                {variant === "danger" || variant === "dangerText"
                  ? texts["delete.confirm"]
                  : texts["header.add"]}
              </Button>
            )),
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button loadingText={texts["upload.saving"]}>{texts["upload.save"]}</Button>
          <Button loading loadingText={texts["upload.saving"]}>
            {texts["upload.save"]}
          </Button>
          <Button disabled disabledReason={texts["upload.save.disabledReason"]}>
            {texts["upload.save"]}
          </Button>
          <Button variant="secondary" icon={Download} disabled>
            {texts["header.export"]}
          </Button>
          <Button variant="tertiary" disabled>
            {texts["filter.resetAll"]}
          </Button>
        </div>
      </Section>
      <Section title="IconButton">
        <div className="flex items-center gap-2">
          <IconButton icon={Eye} aria-label={texts["list.row.open"]} />
          <IconButton icon={MoreHorizontal} aria-label={texts["list.row.more"]} size="sm" />
          <IconButton icon={Download} aria-label={texts["header.export"]} variant="outline" />
          <IconButton
            icon={Trash2}
            aria-label={texts["list.row.menu.delete"]}
            disabled
            disabledReason={texts["offline.disabledReason"]}
          />
        </div>
      </Section>
      <Section title="Input · DateInput · Textarea">
        <Fields />
      </Section>
      <Section title="SegmentedControl · RadioRow · Checkbox">
        <Choices />
      </Section>
      <Section title="Tag · Chip">
        <div className="flex flex-wrap items-center gap-2">
          {(["analysis", "conclusion", "other"] satisfies DocumentType[]).map((type) => (
            <TypeTag key={type} type={type} />
          ))}
          <UndatedTag />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Chip text={t("chip.search", { q: "анализ" })} onRemove={() => undefined} />
          <Chip
            text={t("chip.documentDate.range", { from: "01.04.2026", to: "30.04.2026" })}
            onRemove={() => undefined}
          />
          <Chip text={texts["chip.undated"]} onRemove={() => undefined} />
        </div>
      </Section>
      <Section title="Alert · Banner · Skeleton">
        <Alert
          variant="info"
          action={
            <Button variant="tertiary" size="sm">
              {texts["filter.resetShort"]}
            </Button>
          }
        >
          {t("undated.hint.one", { n: 1 })}
        </Alert>
        <Alert variant="warn" title={errorTitles.version_conflict} />
        <Alert variant="danger" title={texts["upload.file.notPdf"]}>
          {errorTitles.not_pdf}
        </Alert>
        <Alert variant="success">{texts["note.saved"]}</Alert>
        <Banner
          icon={WifiOff}
          title={texts["offline.banner.title"]}
          action={
            <Button variant="secondary" size="sm" icon={RotateCw}>
              {texts["offline.banner.retry"]}
            </Button>
          }
        >
          {texts["offline.banner.text"]}
        </Banner>
        <div
          role="status"
          aria-label={texts["list.skeleton"]}
          className="bg-surface shadow-1 flex items-center gap-3 rounded-xl p-4"
        >
          <Skeleton className="size-9 rounded-md" />
          <div className="flex flex-1 flex-col gap-2">
            <Skeleton className="h-3 w-48" />
            <Skeleton className="h-2.5 w-24" />
          </div>
          <Skeleton className="h-5 w-21" />
        </div>
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-label text-text3">{title}</h2>
      {children}
    </section>
  );
}

function Fields() {
  const [date, setDate] = useState("08.04.2026");
  const [badDate, setBadDate] = useState("31.02.2026");

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Input
        label={texts["search.placeholder"]}
        labelHidden
        placeholder={texts["search.placeholder"]}
        leading={<Search size={16} strokeWidth={1.75} className="text-text3" aria-hidden />}
        trailing={
          <kbd className="border-border text-caption text-text3 rounded-xs border px-1.5 font-mono">
            {texts["search.hotkey"]}
          </kbd>
        }
      />
      <Input
        label={texts["upload.name.label"]}
        hint={texts["upload.name.hint"]}
        defaultValue="Общий анализ крови"
      />
      <Input
        label={texts["upload.name.label"]}
        placeholder={texts["upload.name.placeholder"]}
        error={errorTitles.title_required}
      />
      <Input label={texts["upload.name.label"]} disabled defaultValue="ЭКГ покоя" />
      <DateInput
        label={texts["upload.date.label"]}
        value={date}
        onChange={setDate}
        max="2026-11-10"
      />
      <DateInput
        label={texts["upload.date.label"]}
        value={badDate}
        onChange={setBadDate}
        error={parseDate(badDate) ? undefined : errorTitles.date_invalid}
      />
      <DateInput
        label={texts["upload.date.label"]}
        value={texts["upload.date.noneValue"]}
        onChange={() => undefined}
        disabled
      />
      <Textarea
        label={texts["note.label"]}
        placeholder={texts["note.placeholder"]}
        defaultValue="Пересдать через 3 месяца"
        counter={(n) => t("note.counter", { n })}
      />
    </div>
  );
}

function Choices() {
  const [type, setType] = useState<DocumentType | undefined>("analysis");
  const [dateField, setDateField] = useState<"document" | "uploaded">("document");
  const [scope, setScope] = useState<"filtered" | "all" | "selected">("filtered");

  return (
    <div className="flex flex-col gap-4">
      <SegmentedControl
        label={texts["upload.type.label"]}
        options={TYPE_OPTIONS}
        value={type}
        onValueChange={setType}
        fullWidth
      />
      <SegmentedControl
        label={texts["filter.dateField.label"]}
        options={DATE_FIELD_OPTIONS}
        value={dateField}
        onValueChange={setDateField}
      />
      <SegmentedControl
        aria-label={texts["upload.type.label"]}
        options={TYPE_OPTIONS}
        value={undefined}
        onValueChange={() => undefined}
        error={errorTitles.type_unknown}
      />
      <RadioRowGroup aria-label={texts["export.title"]} value={scope} onValueChange={setScope}>
        <RadioRow
          value="filtered"
          title={texts["export.filtered"]}
          description={t("export.filtered.count", { n: 3, документ: plural(3, plurals.документ) })}
        />
        <RadioRow value="all" title={texts["export.all"]} description={documents(6)} />
        <RadioRow
          value="selected"
          title={texts["export.selected"]}
          description={texts["export.selected.none"]}
          disabled
        />
      </RadioRowGroup>
      <div className="flex flex-wrap items-center gap-6">
        <Checkbox label={texts["upload.date.none"]} />
        <Checkbox label={texts["upload.date.none"]} defaultChecked />
        <Checkbox aria-label={texts["list.selectAll"]} checked="indeterminate" />
        <Checkbox label={texts["upload.date.none"]} disabled />
      </div>
    </div>
  );
}

function Overlays() {
  const showToast = useToast();
  const [formOpen, setFormOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const [title, setTitle] = useState("");
  const [date, setDate] = useState("");

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button variant="secondary" onClick={() => setFormOpen(true)}>
        {texts["upload.title"]}
      </Button>
      <Button variant="dangerText" onClick={() => setDeleteOpen(true)}>
        {texts["doc.delete"]}
      </Button>
      <Button
        variant="secondary"
        onClick={() =>
          showToast({
            title: t("upload.toast.added", { title: SAMPLE_TITLE }),
            action: { label: texts["upload.toast.open"], onClick: () => undefined },
          })
        }
      >
        {texts["upload.toast.open"]}
      </Button>
      <span className="text-caption text-text3">
        {formatSize(79_114)} · {formatSize(2_400_000)}
      </span>

      <Dialog
        open={formOpen}
        onOpenChange={setFormOpen}
        title={texts["upload.title"]}
        description={texts["upload.subtitle"]}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="tertiary">{texts["common.cancel"]}</Button>
            </DialogClose>
            <Button
              disabled={!title}
              disabledReason={texts["upload.save.disabledReason"]}
              loadingText={texts["upload.saving"]}
            >
              {texts["upload.save"]}
            </Button>
          </>
        }
      >
        <Input
          label={texts["upload.name.label"]}
          hint={texts["upload.name.hint"]}
          value={title}
          onChange={(event) => setTitle(event.target.value)}
        />
        <SegmentedControl
          label={texts["upload.type.label"]}
          options={TYPE_OPTIONS}
          value={undefined}
          onValueChange={() => undefined}
          fullWidth
        />
        <DateInput
          label={texts["upload.date.label"]}
          value={date}
          onChange={setDate}
          max="2026-11-10"
        />
      </Dialog>
      <Dialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title={texts["delete.title"]}
        description={t("delete.text", { title: SAMPLE_TITLE, date: "10.04.2026" })}
        width="confirm"
        initialFocus={cancelRef}
        footer={
          <>
            <DialogClose asChild>
              <Button ref={cancelRef} variant="secondary">
                {texts["delete.cancel"]}
              </Button>
            </DialogClose>
            <Button variant="danger" onClick={() => setDeleteOpen(false)}>
              {texts["delete.confirm"]}
            </Button>
          </>
        }
      />
    </div>
  );
}
