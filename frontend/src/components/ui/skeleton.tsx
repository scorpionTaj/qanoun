import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("animate-pulse rounded-xl bg-zellige-100/70 dark:bg-zellige-800/60", className)} {...props} />;
}

export { Skeleton };
