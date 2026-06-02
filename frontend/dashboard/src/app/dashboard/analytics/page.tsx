"use client";
import { Phone, CheckCircle, Clock, Star, TrendingUp } from "lucide-react";
import { MetricCard, Card } from "@/components/ui/card";
import { ChartLine } from "@/components/charts/line-chart";
import { ChartBar } from "@/components/charts/bar-chart";
import { ChartDonut } from "@/components/charts/donut-chart";
import { Badge } from "@/components/ui/badge";

const callVolumeOverTime = [
  { name: "Dec 1", value: 234 }, { name: "Dec 3", value: 298 }, { name: "Dec 5", value: 312 },
  { name: "Dec 7", value: 278 }, { name: "Dec 9", value: 345 }, { name: "Dec 11", value: 389 },
  { name: "Dec 13", value: 412 }, { name: "Dec 15", value: 367 },
];

const channelData = [
  { name: "Voice", value: 1842 },
  { name: "WhatsApp", value: 643 },
  { name: "Chat", value: 521 },
  { name: "SMS", value: 189 },
  { name: "Email", value: 134 },
];

const categoryData = [
  { name: "Billing", value: 38, color: "#3b82f6" },
  { name: "Technical", value: 24, color: "#10b981" },
  { name: "Orders", value: 18, color: "#f59e0b" },
  { name: "Returns", value: 12, color: "#f43f5e" },
  { name: "General", value: 8, color: "#8b5cf6" },
];

const sentimentTrend = [
  { name: "Dec 1", value: 0.68 }, { name: "Dec 3", value: 0.71 }, { name: "Dec 5", value: 0.65 },
  { name: "Dec 7", value: 0.72 }, { name: "Dec 9", value: 0.74 }, { name: "Dec 11", value: 0.69 },
  { name: "Dec 13", value: 0.78 }, { name: "Dec 15", value: 0.75 },
];

const agentLeaderboard = [
  { name: "Ava (AI)", calls: 1284, avgTime: "3:12", csat: 4.6, resolution: "91%", type: "ai" },
  { name: "Nova (AI)", calls: 987, avgTime: "3:45", csat: 4.5, resolution: "89%", type: "ai" },
  { name: "Rachel Kim", calls: 234, avgTime: "5:20", csat: 4.8, resolution: "95%", type: "human" },
  { name: "David Park", calls: 198, avgTime: "4:55", csat: 4.7, resolution: "93%", type: "human" },
  { name: "Lisa Wang", calls: 156, avgTime: "6:10", csat: 4.4, resolution: "87%", type: "human" },
];

export default function AnalyticsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Analytics</h1>
          <p className="text-[var(--foreground-muted)] text-sm mt-1">Performance insights and trends</p>
        </div>
        <div className="flex items-center gap-2 glass px-3 py-1.5 !rounded-lg text-sm">
          <span className="text-[var(--foreground-muted)]">Dec 1 – Dec 15, 2024</span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard label="Total Calls" value="3,329" icon={<Phone className="w-5 h-5" />} accent="primary" trend={{ value: 15, isPositive: true }} />
        <MetricCard label="Resolution Rate" value="88.4%" icon={<CheckCircle className="w-5 h-5" />} accent="accent" trend={{ value: 3.2, isPositive: true }} />
        <MetricCard label="Avg Handle Time" value="4:18" icon={<Clock className="w-5 h-5" />} accent="warning" trend={{ value: 8, isPositive: true }} />
        <MetricCard label="CSAT Score" value="4.6" icon={<Star className="w-5 h-5" />} accent="primary" trend={{ value: 2.1, isPositive: true }} />
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card title="Call Volume Over Time" className="lg:col-span-2">
          <ChartLine data={callVolumeOverTime} showArea color="#3b82f6" height={280} />
        </Card>
        <Card title="Ticket Categories">
          <ChartDonut data={categoryData} height={200} />
          <div className="flex flex-wrap justify-center gap-3 mt-4">
            {categoryData.map((d) => (
              <div key={d.name} className="flex items-center gap-1.5 text-xs">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: d.color }} />
                <span className="text-[var(--foreground-muted)]">{d.name} ({d.value}%)</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Calls by Channel">
          <ChartBar data={channelData} color="#3b82f6" height={260} />
        </Card>
        <Card title="Sentiment Trend">
          <ChartLine data={sentimentTrend} color="#10b981" height={260} />
        </Card>
      </div>

      {/* Agent Leaderboard */}
      <Card title="Agent Performance Leaderboard" noPadding>
        <div className="px-6 pt-6 pb-2 flex items-center justify-between">
          <h3 className="text-lg font-semibold">Agent Performance Leaderboard</h3>
          <Badge variant="info"><TrendingUp className="w-3 h-3 mr-1" /> Top performers</Badge>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[var(--border)]">
                {["Rank", "Agent", "Calls Handled", "Avg Handle Time", "CSAT", "Resolution Rate"].map((h) => (
                  <th key={h} className="text-left px-6 py-3 text-xs font-medium text-[var(--foreground-muted)] uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {agentLeaderboard.map((a, i) => (
                <tr key={a.name} className="hover:bg-white/3 transition-all-200">
                  <td className="px-6 py-4">
                    <span className={`w-7 h-7 rounded-full inline-flex items-center justify-center text-xs font-bold ${i === 0 ? "bg-amber-500/20 text-amber-400" : i === 1 ? "bg-slate-300/20 text-slate-300" : i === 2 ? "bg-orange-600/20 text-orange-400" : "bg-white/5 text-[var(--muted)]"}`}>
                      {i + 1}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${a.type === "ai" ? "bg-gradient-to-br from-blue-500 to-purple-500" : "bg-gradient-to-br from-emerald-500 to-teal-500"}`}>
                        {a.type === "ai" ? "AI" : a.name.charAt(0)}
                      </div>
                      <div>
                        <p className="text-sm font-medium">{a.name}</p>
                        <Badge variant={a.type === "ai" ? "purple" : "default"}>{a.type === "ai" ? "AI Agent" : "Human"}</Badge>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm font-semibold">{a.calls.toLocaleString()}</td>
                  <td className="px-6 py-4 text-sm text-[var(--foreground-muted)]">{a.avgTime}</td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-1">
                      <Star className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />
                      <span className="text-sm font-semibold">{a.csat}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4"><span className="text-sm font-semibold text-[var(--accent)]">{a.resolution}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
