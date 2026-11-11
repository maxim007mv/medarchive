"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { buttonClasses } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { useSession } from "@/lib/api/queries";
import { texts } from "@/lib/texts";

import { LIST_URL_KEY } from "./list-url";

/** The list with the filters it was left with; `/` when it was not opened in this tab. */
export function useListHref(): string {
  const [href, setHref] = useState("/");
  useEffect(() => setHref(sessionStorage.getItem(LIST_URL_KEY) ?? "/"), []);
  return href;
}

/**
 * «← К документам» on every screen but the list; before there is an archive «← На главную»
 * to the start page. Hidden, and out of the tab order, until the session says which one.
 */
export function BackLink({ className }: { className?: string }) {
  const session = useSession();
  const listHref = useListHref();
  const hasArchive = Boolean(session.data);

  return (
    <Link
      href={hasArchive ? listHref : "/"}
      className={cn(
        buttonClasses({ variant: "tertiary", size: "sm" }),
        "self-start",
        session.isPending && "invisible",
        className,
      )}
    >
      <span className="inline-flex items-center gap-2">
        <ArrowLeft size={16} strokeWidth={1.75} aria-hidden />
        {hasArchive ? texts["nav.back.list"] : texts["nav.back.start"]}
      </span>
    </Link>
  );
}
