"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  LayoutDashboard, MessageSquare, Ticket, BarChart3, BookOpen,
  Users, Settings, Phone, Bell, Search, Menu, X, LogOut, ChevronLeft
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useDashboardStore } from "@/lib/store";

const navItems = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/conversations", label: "Conversations", icon: MessageSquare },
  { href: "/dashboard/tickets", label: "Tickets", icon: Ticket },
  { href: "/dashboard/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/dashboard/knowledge", label: "Knowledge Base", icon: BookOpen },
  { href: "/dashboard/agents", label: "Agents", icon: Users },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { sidebarOpen, toggleSidebar } = useDashboardStore();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen flex bg-[var(--background)]">
      {/* Sidebar - Desktop */}
      <aside className={cn(
        "hidden lg:flex flex-col fixed inset-y-0 left-0 z-30 border-r border-[var(--border)] transition-all duration-300",
        "bg-[var(--sidebar-bg)] backdrop-blur-xl",
        sidebarOpen ? "w-64" : "w-20"
      )}>
        {/* Logo */}
        <div className="flex items-center gap-3 px-5 h-16 border-b border-[var(--border)]">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500 to-emerald-500 flex items-center justify-center flex-shrink-0">
            <Phone className="w-4 h-4 text-white" />
          </div>
          {sidebarOpen && <span className="text-lg font-bold gradient-text">VoiceAI</span>}
          <button onClick={toggleSidebar} className="ml-auto text-[var(--muted)] hover:text-[var(--foreground)] transition-colors p-1">
            <ChevronLeft className={cn("w-4 h-4 transition-transform", !sidebarOpen && "rotate-180")} />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all-200",
                  isActive
                    ? "bg-blue-500/15 text-blue-400 shadow-lg shadow-blue-500/10"
                    : "text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-white/5"
                )}
              >
                <item.icon className="w-5 h-5 flex-shrink-0" />
                {sidebarOpen && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* User */}
        <div className="p-3 border-t border-[var(--border)]">
          <div className={cn("flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-white/5 transition-all-200 cursor-pointer")}>
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-xs font-bold flex-shrink-0">A</div>
            {sidebarOpen && (
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">Admin User</p>
                <p className="text-xs text-[var(--foreground-muted)] truncate">admin@voiceai.demo</p>
              </div>
            )}
            {sidebarOpen && <LogOut className="w-4 h-4 text-[var(--muted)]" />}
          </div>
        </div>
      </aside>

      {/* Mobile sidebar */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMobileOpen(false)} />
          <aside className="absolute left-0 inset-y-0 w-64 bg-[var(--sidebar-bg)] backdrop-blur-xl border-r border-[var(--border)] p-3">
            <div className="flex items-center justify-between px-3 py-3 mb-2">
              <span className="text-lg font-bold gradient-text">VoiceAI</span>
              <button onClick={() => setMobileOpen(false)} className="text-[var(--muted)]"><X className="w-5 h-5" /></button>
            </div>
            <nav className="space-y-1">
              {navItems.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <Link key={item.href} href={item.href} onClick={() => setMobileOpen(false)}
                    className={cn(
                      "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all-200",
                      isActive ? "bg-blue-500/15 text-blue-400" : "text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-white/5"
                    )}>
                    <item.icon className="w-5 h-5" />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </nav>
          </aside>
        </div>
      )}

      {/* Main Content */}
      <main className={cn("flex-1 transition-all duration-300", sidebarOpen ? "lg:ml-64" : "lg:ml-20")}>
        {/* Top bar */}
        <header className="sticky top-0 z-20 h-16 flex items-center justify-between px-6 border-b border-[var(--border)] bg-[var(--background)]/80 backdrop-blur-xl">
          <div className="flex items-center gap-4">
            <button onClick={() => setMobileOpen(true)} className="lg:hidden text-[var(--muted)]">
              <Menu className="w-5 h-5" />
            </button>
            <div className="relative hidden sm:block">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted)]" />
              <input type="text" placeholder="Search conversations, tickets..." className="w-72 pl-10 pr-4 py-2 rounded-xl bg-[var(--input-bg)] border border-[var(--border)] text-sm focus:outline-none focus:border-[var(--primary)] transition-all-200" />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button className="relative p-2 rounded-xl hover:bg-white/5 transition-all-200 text-[var(--muted)] hover:text-[var(--foreground)]">
              <Bell className="w-5 h-5" />
              <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-[var(--danger)]" />
            </button>
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-xs font-bold lg:hidden">A</div>
          </div>
        </header>

        {/* Page content */}
        <div className="p-6">{children}</div>
      </main>
    </div>
  );
}
