"use client";
import { BrainCircuit, Phone, Clock, Star } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const agents = [
  { name: "Ava", type: "ai", status: "active", activeCalls: 3, totalCalls: 12840, avgHandleTime: "3:12", csat: 4.6, languages: ["English", "Spanish"] },
  { name: "Nova", type: "ai", status: "active", activeCalls: 2, totalCalls: 9870, avgHandleTime: "3:45", csat: 4.5, languages: ["English", "French"] },
  { name: "Rachel Kim", type: "human", status: "on_call", activeCalls: 1, totalCalls: 2340, avgHandleTime: "5:20", csat: 4.8, languages: ["English", "Korean"] },
  { name: "David Park", type: "human", status: "available", activeCalls: 0, totalCalls: 1980, avgHandleTime: "4:55", csat: 4.7, languages: ["English", "Mandarin"] },
  { name: "Lisa Wang", type: "human", status: "break", activeCalls: 0, totalCalls: 1560, avgHandleTime: "6:10", csat: 4.4, languages: ["English"] },
  { name: "Alex Rivera", type: "human", status: "offline", activeCalls: 0, totalCalls: 890, avgHandleTime: "5:45", csat: 4.3, languages: ["English", "Portuguese"] },
];

const statusColors: Record<string, "success" | "info" | "warning" | "danger" | "default"> = {
  active: "success", on_call: "info", available: "success", break: "warning", offline: "default",
};

export default function AgentsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Agents</h1>
        <p className="text-[var(--foreground-muted)] text-sm mt-1">{agents.filter((a) => a.status !== "offline").length} online • {agents.reduce((s, a) => s + a.activeCalls, 0)} active calls</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {agents.map((a) => (
          <Card key={a.name} className="relative overflow-hidden">
            <div className="flex items-center gap-3 mb-4">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-sm font-bold ${a.type === "ai" ? "bg-gradient-to-br from-blue-500 to-purple-500" : "bg-gradient-to-br from-emerald-500 to-teal-500"}`}>
                {a.type === "ai" ? <BrainCircuit className="w-6 h-6" /> : a.name.split(" ").map((n) => n[0]).join("")}
              </div>
              <div className="flex-1">
                <p className="font-semibold">{a.name}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <Badge variant={a.type === "ai" ? "purple" : "default"}>{a.type === "ai" ? "AI Agent" : "Human"}</Badge>
                  <Badge variant={statusColors[a.status]} dot>{a.status.replace("_", " ")}</Badge>
                </div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-white/5 rounded-lg p-3">
                <div className="flex items-center gap-1.5 text-xs text-[var(--foreground-muted)] mb-1"><Phone className="w-3 h-3" /> Active</div>
                <p className="text-lg font-bold">{a.activeCalls}</p>
              </div>
              <div className="bg-white/5 rounded-lg p-3">
                <div className="flex items-center gap-1.5 text-xs text-[var(--foreground-muted)] mb-1"><Clock className="w-3 h-3" /> Avg Time</div>
                <p className="text-lg font-bold">{a.avgHandleTime}</p>
              </div>
              <div className="bg-white/5 rounded-lg p-3">
                <div className="flex items-center gap-1.5 text-xs text-[var(--foreground-muted)] mb-1"><Star className="w-3 h-3" /> CSAT</div>
                <p className="text-lg font-bold">{a.csat}</p>
              </div>
              <div className="bg-white/5 rounded-lg p-3">
                <div className="flex items-center gap-1.5 text-xs text-[var(--foreground-muted)] mb-1">Total</div>
                <p className="text-lg font-bold">{a.totalCalls.toLocaleString()}</p>
              </div>
            </div>
            <div className="flex gap-1.5 mt-3">
              {a.languages.map((l) => <Badge key={l} variant="default">{l}</Badge>)}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
