"use client";
import { Phone, PhoneIncoming, BrainCircuit, SmilePlus } from "lucide-react";
import { MetricCard, Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChartLine } from "@/components/charts/line-chart";
import { ChartBar } from "@/components/charts/bar-chart";
import { ChartDonut } from "@/components/charts/donut-chart";

// Mock data
const callVolumeData = [
  { name: "Mon", value: 145, value2: 120 },
  { name: "Tue", value: 188, value2: 155 },
  { name: "Wed", value: 221, value2: 178 },
  { name: "Thu", value: 198, value2: 162 },
  { name: "Fri", value: 267, value2: 210 },
  { name: "Sat", value: 89, value2: 72 },
  { name: "Sun", value: 56, value2: 48 },
];

const intentData = [
  { name: "Billing", value: 342 },
  { name: "Orders", value: 281 },
  { name: "Technical", value: 198 },
  { name: "Returns", value: 156 },
  { name: "General", value: 134 },
  { name: "Account", value: 89 },
];

const sentimentData = [
  { name: "Positive", value: 487, color: "#10b981" },
  { name: "Neutral", value: 312, color: "#64748b" },
  { name: "Negative", value: 89, color: "#f43f5e" },
];

const recentConversations = [
  { id: "CVR-1284", customer: "Sarah Johnson", status: "completed", channel: "voice", sentiment: 0.8, duration: "4:32", time: "2 min ago" },
  { id: "CVR-1283", customer: "Mike Chen", status: "in_progress", channel: "voice", sentiment: 0.3, duration: "6:15", time: "5 min ago" },
  { id: "CVR-1282", customer: "Emily Davis", status: "completed", channel: "whatsapp", sentiment: 0.9, duration: "2:48", time: "12 min ago" },
  { id: "CVR-1281", customer: "James Wilson", status: "escalated", channel: "voice", sentiment: -0.4, duration: "8:20", time: "18 min ago" },
  { id: "CVR-1280", customer: "Ana Martinez", status: "completed", channel: "chat", sentiment: 0.6, duration: "3:55", time: "24 min ago" },
];

const activeAgents = [
  { name: "Ava (AI)", status: "active", calls: 3, type: "ai" },
  { name: "Nova (AI)", status: "active", calls: 2, type: "ai" },
  { name: "Rachel Kim", status: "on_call", calls: 1, type: "human" },
  { name: "David Park", status: "available", calls: 0, type: "human" },
  { name: "Lisa Wang", status: "break", calls: 0, type: "human" },
];

const statusColors: Record<string, "success" | "info" | "warning" | "danger" | "default"> = {
  completed: "success", in_progress: "info", escalated: "danger",
  active: "success", on_call: "info", available: "success", break: "warning",
};

function getSentimentEmoji(score: number) {
  if (score > 0.5) return "😊";
  if (score > 0) return "😐";
  if (score > -0.5) return "😕";
  return "😠";
}

export default function DashboardOverview() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard Overview</h1>
        <p className="text-[var(--foreground-muted)] text-sm mt-1">Real-time metrics and insights</p>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Active Calls"
          value={12}
          icon={<Phone className="w-5 h-5" />}
          accent="primary"
          live
          trend={{ value: 18, isPositive: true }}
        />
        <MetricCard
          label="Calls Today"
          value={347}
          icon={<PhoneIncoming className="w-5 h-5" />}
          accent="accent"
          trend={{ value: 12, isPositive: true }}
        />
        <MetricCard
          label="AI Resolution Rate"
          value="87.3%"
          icon={<BrainCircuit className="w-5 h-5" />}
          accent="primary"
          trend={{ value: 5.2, isPositive: true }}
        />
        <MetricCard
          label="Avg Sentiment"
          value="0.72"
          icon={<SmilePlus className="w-5 h-5" />}
          accent="accent"
          trend={{ value: 3.1, isPositive: true }}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card title="Call Volume" subtitle="Last 7 days" className="lg:col-span-2">
          <ChartLine data={callVolumeData} showArea color="#3b82f6" color2="#10b981" height={280} />
        </Card>
        <Card title="Sentiment Distribution">
          <ChartDonut data={sentimentData} height={220} />
          <div className="flex justify-center gap-4 mt-4">
            {sentimentData.map((d) => (
              <div key={d.name} className="flex items-center gap-2 text-xs">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: d.color }} />
                <span className="text-[var(--foreground-muted)]">{d.name}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Top Intents */}
        <Card title="Top Intents">
          <ChartBar data={intentData} height={240} color="#3b82f6" />
        </Card>

        {/* Recent Conversations */}
        <Card title="Recent Conversations" className="lg:col-span-1" noPadding>
          <div className="px-6 pt-6 pb-2">
            <h3 className="text-lg font-semibold">Recent Conversations</h3>
          </div>
          <div className="divide-y divide-[var(--border)]">
            {recentConversations.map((c) => (
              <div key={c.id} className="flex items-center gap-3 px-6 py-3 hover:bg-white/3 transition-all-200 cursor-pointer">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium truncate">{c.customer}</span>
                    <Badge variant={statusColors[c.status]} dot>{c.status.replace("_", " ")}</Badge>
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-[var(--foreground-muted)]">
                    <span>{c.id}</span>
                    <span>•</span>
                    <span>{c.duration}</span>
                    <span>•</span>
                    <span>{c.time}</span>
                  </div>
                </div>
                <span className="text-lg">{getSentimentEmoji(c.sentiment)}</span>
              </div>
            ))}
          </div>
        </Card>

        {/* Active Agents */}
        <Card title="Active Agents" noPadding>
          <div className="px-6 pt-6 pb-2 flex items-center justify-between">
            <h3 className="text-lg font-semibold">Active Agents</h3>
            <Badge variant="info" dot>{activeAgents.filter((a) => a.status === "active" || a.status === "on_call").length} online</Badge>
          </div>
          <div className="divide-y divide-[var(--border)]">
            {activeAgents.map((a) => (
              <div key={a.name} className="flex items-center gap-3 px-6 py-3">
                <div className={`w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold ${a.type === "ai" ? "bg-gradient-to-br from-blue-500 to-purple-500" : "bg-gradient-to-br from-emerald-500 to-teal-500"}`}>
                  {a.type === "ai" ? <BrainCircuit className="w-4 h-4" /> : a.name.charAt(0)}
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium">{a.name}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <Badge variant={statusColors[a.status]} dot>{a.status.replace("_", " ")}</Badge>
                    {a.calls > 0 && <span className="text-xs text-[var(--foreground-muted)]">{a.calls} active</span>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
