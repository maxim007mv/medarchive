import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export type BannerProps = {
  icon?: LucideIcon;
  /** Bold lead, e.g. «Нет связи с сервером.» */
  title?: string;
  children: ReactNode;
  /** A small secondary button, e.g. «Повторить». */
  action?: ReactNode;
};

/** Full-width warning strip under the header (D14). Announced politely when it appears. */
export function Banner({ icon: Icon, title, children, action }: BannerProps) {
  return (
    <div
      role="status"
      className="border-border bg-warn-bg text-label text-warn flex items-center gap-3 border-b px-4 py-2.5 font-normal md:px-8"
    >
      {Icon && <Icon size={16} strokeWidth={1.75} className="shrink-0" aria-hidden />}
      <p className="min-w-0 flex-1">
        {title && <strong className="font-semibold">{title}</strong>} {children}
      </p>
      {action}
    </div>
  );
}
