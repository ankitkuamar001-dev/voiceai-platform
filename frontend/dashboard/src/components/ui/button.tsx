import { cn } from "@/lib/utils";
import { ButtonHTMLAttributes, forwardRef } from "react";

const buttonVariants = {
  primary: "bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white shadow-lg shadow-blue-500/25",
  secondary: "bg-[var(--card)] hover:bg-[var(--card-hover)] text-[var(--foreground)] border border-[var(--card-border)]",
  ghost: "bg-transparent hover:bg-white/5 text-[var(--foreground-muted)] hover:text-[var(--foreground)]",
  danger: "bg-[var(--danger)] hover:bg-rose-600 text-white shadow-lg shadow-rose-500/25",
  accent: "bg-[var(--accent)] hover:bg-emerald-600 text-white shadow-lg shadow-emerald-500/25",
};

const buttonSizes = {
  sm: "px-3 py-1.5 text-xs rounded-lg",
  md: "px-4 py-2.5 text-sm rounded-xl",
  lg: "px-6 py-3 text-base rounded-xl",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof buttonVariants;
  size?: keyof typeof buttonSizes;
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", loading, children, disabled, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center gap-2 font-medium transition-all-200 cursor-pointer",
        "disabled:opacity-50 disabled:pointer-events-none",
        buttonVariants[variant],
        buttonSizes[size],
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      )}
      {children}
    </button>
  )
);
Button.displayName = "Button";
