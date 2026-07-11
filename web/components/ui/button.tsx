"use client";

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { motion, useReducedMotion } from "framer-motion";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-xl font-body text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary:
          "bg-accent text-ink hover:bg-accent-soft shadow-[0_0_24px_rgba(139,147,248,0.25)]",
        ghost:
          "border border-ink-line bg-slate-900/40 text-slate-200 backdrop-blur-md hover:border-accent/40 hover:text-white",
        subtle: "text-slate-300 hover:text-white hover:bg-white/5",
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-10 px-5",
        lg: "h-12 px-7 text-base",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /** Framer-motion hover lift (disabled automatically for reduced motion). */
  magnetic?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, magnetic = true, children, ...props }, ref) => {
    const reduce = useReducedMotion();
    if (magnetic && !reduce) {
      const { onDrag, onDragStart, onDragEnd, onAnimationStart, ...rest } = props;
      return (
        <motion.button
          ref={ref}
          whileHover={{ scale: 1.03, y: -1 }}
          whileTap={{ scale: 0.98 }}
          transition={{ type: "spring", stiffness: 400, damping: 22 }}
          className={cn(buttonVariants({ variant, size }), className)}
          {...rest}
        >
          {children}
        </motion.button>
      );
    }
    return (
      <button
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      >
        {children}
      </button>
    );
  },
);
Button.displayName = "Button";
