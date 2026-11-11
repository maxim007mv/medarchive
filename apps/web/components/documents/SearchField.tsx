"use client";

import { Search, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { IconButton } from "@/components/ui/icon-button";
import { Input } from "@/components/ui/input";
import { countQueryChars, MIN_QUERY_CHARS } from "@/lib/filters";
import { texts } from "@/lib/texts";

export const SEARCH_DEBOUNCE_MS = 250;

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

/**
 * Search of D06 (FE-14): the query reaches the URL 250 ms after typing stops and only from
 * 3 characters; `/` anywhere on the page focuses the field.
 */
export function SearchField({ value, onCommit }: { value: string; onCommit: (q: string) => void }) {
  const [text, setText] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);
  const tooShort = countQueryChars(text) > 0 && countQueryChars(text) < MIN_QUERY_CHARS;

  useEffect(() => setText(value), [value]);

  useEffect(() => {
    if (text === value || tooShort) return;
    const timer = setTimeout(
      () => onCommit(countQueryChars(text) === 0 ? "" : text),
      SEARCH_DEBOUNCE_MS,
    );
    return () => clearTimeout(timer);
  }, [text, value, tooShort, onCommit]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (
        event.key !== "/" ||
        event.metaKey ||
        event.ctrlKey ||
        event.altKey ||
        isTypingTarget(event.target)
      )
        return;
      event.preventDefault();
      inputRef.current?.focus();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  function clear() {
    setText("");
    onCommit("");
    inputRef.current?.focus();
  }

  return (
    <Input
      ref={inputRef}
      // Not type="search": its native cancel button would duplicate «Очистить поиск».
      type="text"
      role="searchbox"
      enterKeyHint="search"
      label={texts["search.placeholder"]}
      labelHidden
      placeholder={texts["search.placeholder"]}
      value={text}
      onChange={(event) => setText(event.target.value)}
      maxLength={100}
      hint={tooShort ? texts["search.tooShort"] : undefined}
      aria-keyshortcuts="/"
      leading={<Search size={16} strokeWidth={1.75} className="text-text2 shrink-0" aria-hidden />}
      trailing={
        text ? (
          <IconButton
            icon={X}
            size="sm"
            aria-label={texts["search.clear"]}
            onClick={clear}
            className="-mr-2"
          />
        ) : (
          <kbd
            className="border-border text-caption text-text3 rounded-xs border px-1.5 font-mono"
            aria-hidden
          >
            {texts["search.hotkey"]}
          </kbd>
        )
      }
    />
  );
}
