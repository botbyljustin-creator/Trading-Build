import clsx from "clsx";
import { forwardRef, type InputHTMLAttributes, type TextareaHTMLAttributes } from "react";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={clsx(
        "w-full rounded-md border border-base-600 bg-base-850 px-3 py-1.5 text-sm text-slate-100 placeholder:text-slate-600 focus:border-accent-info focus:outline-none",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={clsx(
        "w-full rounded-md border border-base-600 bg-base-850 px-3 py-1.5 text-sm text-slate-100 placeholder:text-slate-600 focus:border-accent-info focus:outline-none",
        className,
      )}
      {...props}
    />
  ),
);
Textarea.displayName = "Textarea";

export function Label({ children }: { children: React.ReactNode }) {
  return <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">{children}</label>;
}
