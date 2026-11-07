import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        default:
          "bg-zellige-100 text-zellige-800 dark:bg-zellige-800/80 dark:text-zellige-100",
        outline:
          "border border-zellige-200 text-zellige-700 dark:border-zellige-700 dark:text-zellige-200",
        sand: "bg-sand-100 text-sand-800 dark:bg-sand-900/60 dark:text-sand-200",
        domain: "bg-zellige-700 text-white dark:bg-zellige-600",
        secondary: "bg-sand-500 text-white",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
