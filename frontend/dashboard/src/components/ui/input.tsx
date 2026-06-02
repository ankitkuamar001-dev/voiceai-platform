import { cn } from "@/lib/utils";
import { InputHTMLAttributes, forwardRef } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, ...props }, ref) => (
    <div className="space-y-1.5">
      {label && <label className="block text-sm font-medium text-[var(--foreground-muted)]">{label}</label>}
      <input
        ref={ref}
        className={cn(
          "w-full px-4 py-2.5 rounded-xl text-sm",
          "bg-[var(--input-bg)] border border-[var(--border)]",
          "text-[var(--foreground)] placeholder:text-[var(--muted)]",
          "focus:outline-none focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)]",
          "transition-all-200",
          error && "border-[var(--danger)]",
          className
        )}
        {...props}
      />
      {error && <p className="text-xs text-[var(--danger)]">{error}</p>}
    </div>
  )
);
Input.displayName = "Input";
