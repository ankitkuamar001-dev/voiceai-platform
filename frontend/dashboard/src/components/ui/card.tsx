import { cn } from "@/lib/utils";
import { ReactNode } from "react";

interface CardProps {
  title?: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
  glow?: boolean;
  noPadding?: boolean;
}

export function Card({ title, subtitle, children, className, glow, noPadding }: CardProps) {
  return (
    <div
      className={cn(
        "glass glass-hover transition-all-200",
        glow && "glow-primary",
        !noPadding && "p-6",
        className
      )}
    >
      {(title || subtitle) && (
        <div className="mb-4">
          {title && <h3 className="text-lg font-semibold text-[var(--foreground)]">{title}</h3>}
          {subtitle && <p className="text-sm text-[var(--foreground-muted)] mt-1">{subtitle}</p>}
        </div>
      )}
      {children}
    </div>
  );
}

interface MetricCardProps {
  label: string;
  value: string | number;
  trend?: { value: number; isPositive: boolean };
  icon: ReactNode;
  accent?: "primary" | "accent" | "danger" | "warning";
  live?: boolean;
}

export function MetricCard({ label, value, trend, icon, accent = "primary", live }: MetricCardProps) {
  const accentColors = {
    primary: "text-[var(--primary)]",
    accent: "text-[var(--accent)]",
    danger: "text-[var(--danger)]",
    warning: "text-[var(--warning)]",
  };

  return (
    <div className="glass glass-hover transition-all-200 p-6 relative overflow-hidden">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-[var(--foreground-muted)] mb-1 flex items-center gap-2">
            {label}
            {live && (
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--accent)] opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-[var(--accent)]"></span>
              </span>
            )}
          </p>
          <p className="text-3xl font-bold mt-2">{value}</p>
          {trend && (
            <p className={cn("text-sm mt-2 font-medium", trend.isPositive ? "text-[var(--accent)]" : "text-[var(--danger)]")}>
              {trend.isPositive ? "↑" : "↓"} {Math.abs(trend.value)}% vs last week
            </p>
          )}
        </div>
        <div className={cn("p-3 rounded-xl bg-opacity-10", accentColors[accent])} style={{ backgroundColor: `var(--${accent}-glow)` }}>
          {icon}
        </div>
      </div>
      <div className="absolute -bottom-4 -right-4 w-24 h-24 rounded-full opacity-5" style={{ background: `var(--${accent})` }} />
    </div>
  );
}
