import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zellige-500 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default:
          "bg-zellige-700 text-white shadow hover:bg-zellige-800 dark:bg-zellige-500 dark:hover:bg-zellige-400 dark:text-zellige-950",
        secondary:
          "bg-zellige-100 text-zellige-900 hover:bg-zellige-200 dark:bg-zellige-800 dark:text-zellige-100 dark:hover:bg-zellige-700",
        outline:
          "border border-zellige-200 bg-white hover:bg-zellige-50 text-zellige-900 dark:border-zellige-700 dark:bg-transparent dark:text-zellige-100 dark:hover:bg-zellige-800/60",
        ghost:
          "hover:bg-zellige-100 text-zellige-900 dark:text-zellige-100 dark:hover:bg-zellige-800/60",
        sand: "bg-sand-500 text-white hover:bg-sand-600 dark:bg-sand-500 dark:hover:bg-sand-400 dark:text-zellige-950",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 rounded-lg px-3 text-xs",
        lg: "h-12 rounded-xl px-6 text-base",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button className={cn(buttonVariants({ variant, size }), className)} ref={ref} {...props} />
  )
);
Button.displayName = "Button";

export { Button, buttonVariants };
