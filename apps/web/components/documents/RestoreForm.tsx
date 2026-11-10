"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useOpenByKey } from "@/lib/api/queries";
import { texts } from "@/lib/texts";

import { useProblem } from "./use-problem";

const KEY_LENGTH = 24;
const GROUP = 4;

/** `7k3m q9tb…` or without dashes → `7K3M-Q9TB-…`; anything else is sent as typed and the server answers. */
export function normalizeAccessKey(input: string): string {
  const compact = input.toUpperCase().replace(/[^0-9A-Z]/g, "");
  if (compact.length !== KEY_LENGTH) return input.trim();
  return compact.match(new RegExp(`.{${GROUP}}`, "g"))?.join("-") ?? compact;
}

/** «Открыть архив по ключу» (FE-22, TC-081, TC-082): 401 and 429 texts go under the field. */
export function RestoreForm() {
  const router = useRouter();
  const [accessKey, setAccessKey] = useState("");
  const openByKey = useOpenByKey();
  const problem = useProblem(openByKey.error);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (problem?.waitSeconds) return;
    openByKey.mutate(normalizeAccessKey(accessKey), { onSuccess: () => router.push("/") });
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
      <Input
        label={texts["restore.label"]}
        hint={texts["restore.hint"]}
        error={problem?.title}
        value={accessKey}
        onChange={(event) => setAccessKey(event.target.value)}
        autoComplete="off"
        autoCapitalize="characters"
        spellCheck={false}
        className="font-mono"
      />
      <Button
        type="submit"
        loading={openByKey.isPending}
        disabled={!accessKey.trim() || Boolean(problem?.waitSeconds)}
        className="self-start"
      >
        {texts["restore.submit"]}
      </Button>
    </form>
  );
}
