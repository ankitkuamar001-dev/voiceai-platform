"use client";
import { useState } from "react";
import { Search, Plus, AlertTriangle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const mockTickets = [
  { id: "TKT-1042", subject: "Unable to process payment", status: "open", priority: 1, customer: "James Wilson", assignee: "Rachel Kim", category: "Billing", created: "15 min ago", sla: false },
  { id: "TKT-1041", subject: "Product arrived damaged", status: "in_progress", priority: 2, customer: "Tom Brown", assignee: "David Park", category: "Returns", created: "1 hour ago", sla: false },
  { id: "TKT-1040", subject: "Feature request: dark mode", status: "open", priority: 4, customer: "Lisa Wong", assignee: "—", category: "Feature Request", created: "2 hours ago", sla: false },
  { id: "TKT-1039", subject: "Account locked after password reset", status: "escalated", priority: 1, customer: "Robert Taylor", assignee: "Rachel Kim", category: "Technical", created: "3 hours ago", sla: true },
  { id: "TKT-1038", subject: "Subscription upgrade not reflected", status: "waiting_on_customer", priority: 3, customer: "Maria Garcia", assignee: "Ava (AI)", category: "Billing", created: "5 hours ago", sla: false },
  { id: "TKT-1037", subject: "API rate limit exceeded", status: "in_progress", priority: 2, customer: "Kevin Lee", assignee: "David Park", category: "Technical", created: "8 hours ago", sla: false },
  { id: "TKT-1036", subject: "Refund not received after 14 days", status: "escalated", priority: 1, customer: "Sarah Johnson", assignee: "Rachel Kim", category: "Billing", created: "1 day ago", sla: true },
  { id: "TKT-1035", subject: "Mobile app crashing on login", status: "resolved", priority: 2, customer: "Mike Chen", assignee: "David Park", category: "Technical", created: "2 days ago", sla: false },
  { id: "TKT-1034", subject: "Update shipping address", status: "closed", priority: 4, customer: "Emily Davis", assignee: "Nova (AI)", category: "Orders", created: "3 days ago", sla: false },
];

const statusColors: Record<string, "success" | "info" | "warning" | "danger" | "default" | "purple"> = {
  open: "info", in_progress: "warning", waiting_on_customer: "default",
  escalated: "danger", resolved: "success", closed: "default",
};

const priorityConfig: Record<number, { label: string; variant: "danger" | "warning" | "info" | "success" }> = {
  1: { label: "P1 Critical", variant: "danger" },
  2: { label: "P2 High", variant: "warning" },
  3: { label: "P3 Medium", variant: "info" },
  4: { label: "P4 Low", variant: "success" },
};

export default function TicketsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const filtered = mockTickets.filter((t) => {
    if (statusFilter !== "all" && t.status !== statusFilter) return false;
    if (search && !t.subject.toLowerCase().includes(search.toLowerCase()) && !t.id.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Tickets</h1>
          <p className="text-[var(--foreground-muted)] text-sm mt-1">{mockTickets.length} total tickets • {mockTickets.filter((t) => t.sla).length} SLA breaches</p>
        </div>
        <Button size="md"><Plus className="w-4 h-4 mr-1" /> New Ticket</Button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted)]" />
          <input type="text" placeholder="Search tickets..." value={search} onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-xl bg-[var(--input-bg)] border border-[var(--border)] text-sm focus:outline-none focus:border-[var(--primary)] transition-all-200" />
        </div>
        <div className="flex gap-2 flex-wrap">
          {["all", "open", "in_progress", "escalated", "resolved", "closed"].map((s) => (
            <button key={s} onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all-200 ${statusFilter === s ? "bg-[var(--primary)] text-white" : "bg-white/5 text-[var(--foreground-muted)] hover:bg-white/10"}`}>
              {s === "all" ? "All" : s.replace(/_/g, " ")}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <Card noPadding>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[var(--border)]">
                {["#", "Subject", "Status", "Priority", "Customer", "Assignee", "Category", "Created"].map((h) => (
                  <th key={h} className="text-left px-6 py-3 text-xs font-medium text-[var(--foreground-muted)] uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {filtered.map((t) => (
                <tr key={t.id} className="hover:bg-white/3 transition-all-200 cursor-pointer">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-mono text-[var(--primary)]">{t.id}</span>
                      {t.sla && <AlertTriangle className="w-3.5 h-3.5 text-[var(--danger)]" />}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <p className="text-sm font-medium max-w-[250px] truncate">{t.subject}</p>
                  </td>
                  <td className="px-6 py-4"><Badge variant={statusColors[t.status]} dot>{t.status.replace(/_/g, " ")}</Badge></td>
                  <td className="px-6 py-4"><Badge variant={priorityConfig[t.priority]?.variant}>{priorityConfig[t.priority]?.label}</Badge></td>
                  <td className="px-6 py-4 text-sm">{t.customer}</td>
                  <td className="px-6 py-4 text-sm text-[var(--foreground-muted)]">{t.assignee}</td>
                  <td className="px-6 py-4"><Badge variant="default">{t.category}</Badge></td>
                  <td className="px-6 py-4 text-xs text-[var(--foreground-muted)]">{t.created}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
