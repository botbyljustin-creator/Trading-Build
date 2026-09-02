"use client";

import clsx from "clsx";
import { forwardRef, type ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost";

const variantClasses: Record<Variant, string> = {
  primary: "bg-accent-info text-white hover:bg-blue-600 disabled:bg-blue-900/50",
  secondary: "bg-base-800 text-slate-200 hover:bg-base-700 border border-base-600",
  danger: "bg-accent-short/10 text-accent-short hover:bg-accent-short/20 border border-accent-short/30",
  ghost: "text-slate-400 hover:text-slate-100 hover:bg-base-800",
};

export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }>(
  ({ className, variant = "primary", disabled, children, ...props }, ref) => (
    <button
      ref={ref}
      disabled={disabled}
      className={clsx(
        "inline-flex items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60",
        variantClasses[variant],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  ),
);
Button.displayName = "Button";
