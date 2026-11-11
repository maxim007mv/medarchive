"use client";

import { Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";

import { texts } from "@/lib/texts";

import { IconButton } from "./icon-button";
import { applyTheme, type Theme } from "./theme";

function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributeFilter: ["data-theme"] });
  return () => observer.disconnect();
}

function currentTheme(): Theme {
  const theme = document.documentElement.dataset.theme;
  if (theme === "light" || theme === "dark") return theme;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** Header switch (FE-01). The server does not know the theme, so it renders the light variant. */
export function ThemeToggle() {
  const theme = useSyncExternalStore(subscribe, currentTheme, () => "light" as const);
  const isDark = theme === "dark";

  return (
    <IconButton
      icon={isDark ? Sun : Moon}
      aria-label={isDark ? texts["header.theme.light"] : texts["header.theme.dark"]}
      onClick={() => applyTheme(isDark ? "light" : "dark")}
    />
  );
}
