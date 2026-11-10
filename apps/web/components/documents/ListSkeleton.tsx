import { Skeleton } from "@/components/ui/skeleton";
import { texts } from "@/lib/texts";

const ROWS = 6;

/** D13: the shape of the rows, shown only when the list takes longer than 1 s. */
export function ListSkeleton() {
  return (
    <div
      role="status"
      aria-label={texts["list.skeleton"]}
      className="border-border bg-surface shadow-1 flex flex-col overflow-hidden rounded-xl border"
    >
      {Array.from({ length: ROWS }, (_, index) => (
        <div
          key={index}
          className="border-border flex items-center gap-4 border-b px-4 py-3 last:border-b-0"
        >
          <Skeleton className="size-4" />
          <Skeleton className="size-icon-button-sm rounded-md" />
          <div className="flex flex-1 flex-col gap-1.5">
            <Skeleton className="h-3.5 w-1/3" />
            <Skeleton className="h-3 w-1/5" />
          </div>
          <Skeleton className="hidden h-6 w-24 lg:block" />
          <Skeleton className="hidden h-3.5 w-20 lg:block" />
          <Skeleton className="hidden h-3.5 w-32 lg:block" />
        </div>
      ))}
    </div>
  );
}
