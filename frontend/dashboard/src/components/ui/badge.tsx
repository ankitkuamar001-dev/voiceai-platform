import { cn } from "@/lib/utils";

const variants = {
  success: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  warning: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  danger: "bg-rose-500/15 text-rose-400 border-rose-500/30",
  info: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  default: "bg-slate-500/15 text-slate-400 border-slate-500/30",
  purple: "bg-purple-500/15 text-purple-400 border-purple-500/30",
};

interface BadgeProps {
  children: React.ReactNode;
  variant?: keyof typeof variants;
  dot?: boolean;
  className?: string;
}

export function Badge({ children, variant = "default", dot, className }: BadgeProps) {
  return (
    <span className={cn(
      "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border",
      variants[variant],
      className
    )}>
      {dot && <span className={cn("w-1.5 h-1.5 rounded-full", {
        "bg-emerald-400": variant === "success",
        "bg-amber-400": variant === "warning",
        "bg-rose-400": variant === "danger",
        "bg-blue-400": variant === "info",
        "bg-slate-400": variant === "default",
        "bg-purple-400": variant === "purple",
      })} />}
      {children}
    </span>
  );
}
