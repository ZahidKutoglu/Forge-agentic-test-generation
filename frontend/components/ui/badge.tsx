import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-sm border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider",
  {
    variants: {
      variant: {
        default: "border-zinc-800 bg-zinc-900 text-zinc-400",
        pass: "border-emerald-900/80 bg-emerald-950/60 text-emerald-400",
        fail: "border-red-900/80 bg-red-950/50 text-red-400",
        run: "border-amber-900/80 bg-amber-950/50 text-amber-400",
        idle: "border-zinc-800 bg-transparent text-zinc-500",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}
