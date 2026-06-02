"use client";
import { useState } from "react";
import { Search, Phone, MessageSquare, Mail, MessageCircle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";

const mockConversations = [
  { id: "CVR-1284", customer: "Sarah Johnson", phone: "+1-555-0101", status: "completed", channel: "voice", sentiment: 0.82, duration: "4:32", agent: "Ava (AI)", ai_confidence: 0.94, time: "2024-12-15 14:32" },
  { id: "CVR-1283", customer: "Mike Chen", phone: "+1-555-0102", status: "in_progress", channel: "voice", sentiment: 0.31, duration: "6:15", agent: "Ava (AI)", ai_confidence: 0.78, time: "2024-12-15 14:28" },
  { id: "CVR-1282", customer: "Emily Davis", phone: "+1-555-0103", status: "completed", channel: "whatsapp", sentiment: 0.91, duration: "2:48", agent: "Nova (AI)", ai_confidence: 0.96, time: "2024-12-15 14:20" },
  { id: "CVR-1281", customer: "James Wilson", phone: "+1-555-0104", status: "escalated", channel: "voice", sentiment: -0.42, duration: "8:20", agent: "Rachel Kim", ai_confidence: 0.45, time: "2024-12-15 14:12" },
  { id: "CVR-1280", customer: "Ana Martinez", phone: "+1-555-0105", status: "completed", channel: "chat", sentiment: 0.65, duration: "3:55", agent: "Ava (AI)", ai_confidence: 0.88, time: "2024-12-15 14:05" },
  { id: "CVR-1279", customer: "Tom Brown", phone: "+1-555-0106", status: "completed", channel: "voice", sentiment: 0.73, duration: "5:10", agent: "Nova (AI)", ai_confidence: 0.91, time: "2024-12-15 13:58" },
  { id: "CVR-1278", customer: "Lisa Wong", phone: "+1-555-0107", status: "failed", channel: "voice", sentiment: -0.15, duration: "0:45", agent: "System", ai_confidence: 0.0, time: "2024-12-15 13:50" },
  { id: "CVR-1277", customer: "Robert Taylor", phone: "+1-555-0108", status: "completed", channel: "sms", sentiment: 0.55, duration: "2:20", agent: "Ava (AI)", ai_confidence: 0.85, time: "2024-12-15 13:42" },
  { id: "CVR-1276", customer: "Maria Garcia", phone: "+1-555-0109", status: "queued", channel: "voice", sentiment: 0.0, duration: "0:00", agent: "—", ai_confidence: 0.0, time: "2024-12-15 13:38" },
  { id: "CVR-1275", customer: "Kevin Lee", phone: "+1-555-0110", status: "completed", channel: "voice", sentiment: 0.88, duration: "3:15", agent: "Ava (AI)", ai_confidence: 0.97, time: "2024-12-15 13:30" },
];

const statusMap: Record<string, { variant: "success" | "info" | "warning" | "danger" | "default"; label: string }> = {
  completed: { variant: "success", label: "Completed" },
  in_progress: { variant: "info", label: "In Progress" },
  queued: { variant: "warning", label: "Queued" },
  escalated: { variant: "danger", label: "Escalated" },
  failed: { variant: "danger", label: "Failed" },
};

const channelIcons: Record<string, React.ReactNode> = {
  voice: <Phone className="w-3.5 h-3.5" />,
  chat: <MessageSquare className="w-3.5 h-3.5" />,
  whatsapp: <MessageCircle className="w-3.5 h-3.5" />,
  email: <Mail className="w-3.5 h-3.5" />,
  sms: <MessageSquare className="w-3.5 h-3.5" />,
};

function SentimentBar({ score }: { score: number }) {
  const normalized = ((score + 1) / 2) * 100;
  const color = score > 0.5 ? "#10b981" : score > 0 ? "#f59e0b" : "#f43f5e";
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 rounded-full bg-white/10 overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${normalized}%`, backgroundColor: color }} />
      </div>
      <span className="text-xs text-[var(--foreground-muted)]">{score.toFixed(2)}</span>
    </div>
  );
}

export default function ConversationsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const filtered = mockConversations.filter((c) => {
    if (statusFilter !== "all" && c.status !== statusFilter) return false;
    if (search && !c.customer.toLowerCase().includes(search.toLowerCase()) && !c.id.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Conversations</h1>
          <p className="text-[var(--foreground-muted)] text-sm mt-1">{mockConversations.length} total conversations</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted)]" />
          <input
            type="text" placeholder="Search by customer or ID..."
            value={search} onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-xl bg-[var(--input-bg)] border border-[var(--border)] text-sm focus:outline-none focus:border-[var(--primary)] transition-all-200"
          />
        </div>
        <div className="flex gap-2">
          {["all", "completed", "in_progress", "escalated", "queued", "failed"].map((s) => (
            <button key={s} onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all-200 ${statusFilter === s ? "bg-[var(--primary)] text-white" : "bg-white/5 text-[var(--foreground-muted)] hover:bg-white/10"}`}>
              {s === "all" ? "All" : s.replace("_", " ")}
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
                {["ID", "Customer", "Status", "Channel", "Sentiment", "Duration", "Agent", "Time"].map((h) => (
                  <th key={h} className="text-left px-6 py-3 text-xs font-medium text-[var(--foreground-muted)] uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {filtered.map((c) => (
                <tr key={c.id} className="hover:bg-white/3 transition-all-200 cursor-pointer group">
                  <td className="px-6 py-4">
                    <Link href={`/dashboard/conversations/${c.id}`} className="text-sm font-mono text-[var(--primary)]">{c.id}</Link>
                  </td>
                  <td className="px-6 py-4">
                    <p className="text-sm font-medium">{c.customer}</p>
                    <p className="text-xs text-[var(--foreground-muted)]">{c.phone}</p>
                  </td>
                  <td className="px-6 py-4"><Badge variant={statusMap[c.status]?.variant} dot>{statusMap[c.status]?.label}</Badge></td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-1.5 text-[var(--foreground-muted)]">
                      {channelIcons[c.channel]}
                      <span className="text-xs capitalize">{c.channel}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4"><SentimentBar score={c.sentiment} /></td>
                  <td className="px-6 py-4 text-sm text-[var(--foreground-muted)]">{c.duration}</td>
                  <td className="px-6 py-4 text-sm">{c.agent}</td>
                  <td className="px-6 py-4 text-xs text-[var(--foreground-muted)]">{c.time}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
