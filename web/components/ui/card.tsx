import * as React from "react";
import { cn } from "@/lib/utils";

/** The one glass card. All panels in the app use this treatment. */
export function GlassCard({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("glass glass-pad", className)} {...props}>
      {children}
    </div>
  );
}

export function CardTitle({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3 className={cn("type-card-title text-slate-100", className)} {...props}>
      {children}
    </h3>
  );
}
