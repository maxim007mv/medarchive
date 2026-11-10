"use client";

import { Download, FolderClosed, KeyRound, Plus } from "lucide-react";
import Link from "next/link";

import { Button, buttonClasses } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { texts } from "@/lib/texts";

type Actions = {
  onExport: () => void;
  onAdd: () => void;
  /** Why «Экспорт» is unavailable: empty archive or no connection. */
  exportDisabledReason?: string;
  addDisabledReason?: string;
};

/**
 * Top bar of every screen. Without `actions` (onboarding, policy) only the brand and the theme
 * switch are shown. On phones «Добавить PDF» moves to the pinned bottom bar (M02).
 */
export function AppHeader({
  actions,
  showSettings = false,
}: {
  actions?: Actions;
  showSettings?: boolean;
}) {
  return (
    <>
      <header className="pt-safe border-border bg-surface sticky top-0 z-20 border-b">
        <div className="flex h-16 items-center gap-4 px-4 lg:px-6">
          <Link href="/" className="flex items-center gap-2.5 rounded-md">
            <span
              className="bg-accent text-on-primary grid size-8 place-items-center rounded-md"
              aria-hidden
            >
              <FolderClosed size={16} strokeWidth={1.75} />
            </span>
            <span className="text-h3">{texts["app.name"]}</span>
          </Link>
          <span className="text-caption text-text3 hidden lg:inline">{texts["app.tagline"]}</span>

          <div className="ml-auto flex items-center gap-2">
            <ThemeToggle />
            {showSettings && (
              <Link
                href="/settings"
                aria-label={texts["settings.title"]}
                title={texts["settings.title"]}
                className={buttonClasses({ variant: "tertiary", size: "md" })}
              >
                <KeyRound size={20} strokeWidth={1.75} aria-hidden />
              </Link>
            )}
            {actions && (
              <>
                <IconButton
                  icon={Download}
                  aria-label={texts["header.export"]}
                  disabled={Boolean(actions.exportDisabledReason)}
                  disabledReason={actions.exportDisabledReason}
                  onClick={actions.onExport}
                  className="md:hidden"
                />
                <Button
                  variant="secondary"
                  icon={Download}
                  disabled={Boolean(actions.exportDisabledReason)}
                  disabledReason={actions.exportDisabledReason}
                  onClick={actions.onExport}
                  className="hidden md:inline-grid"
                >
                  {texts["header.export"]}
                </Button>
                <Button
                  icon={Plus}
                  disabled={Boolean(actions.addDisabledReason)}
                  disabledReason={actions.addDisabledReason}
                  onClick={actions.onAdd}
                  className="hidden md:inline-grid"
                >
                  {texts["header.add"]}
                </Button>
              </>
            )}
          </div>
        </div>
      </header>
      {actions && (
        <div className="pb-safe from-bg fixed inset-x-0 bottom-0 z-20 bg-linear-to-t from-60% to-transparent px-4 pt-6 md:hidden">
          <Button
            size="lg"
            icon={Plus}
            disabled={Boolean(actions.addDisabledReason)}
            disabledReason={actions.addDisabledReason}
            onClick={actions.onAdd}
            className="w-full"
          >
            {texts["header.add"]}
          </Button>
        </div>
      )}
    </>
  );
}
