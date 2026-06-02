"use client";
import { use } from "react";
import { ArrowLeft, Phone, Clock, BrainCircuit, AlertTriangle, Ticket as TicketIcon } from "lucide-react";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const mockMessages = [
  { id: 1, sender: "system", content: "Call connected via voice channel", type: "system" },
  { id: 2, sender: "ai_bot", content: "Hello! Thank you for calling. My name is Ava, your virtual support assistant. How can I help you today?", type: "agent" },
  { id: 3, sender: "customer", content: "Hi, I placed an order last week and it still hasn't arrived. The order number is ORD-78234.", type: "customer" },
  { id: 4, sender: "ai_bot", content: "I'm sorry to hear about the delay with your order, Sarah. Let me look up order ORD-78234 for you right away.", type: "agent" },
  { id: 5, sender: "system", content: "Tool called: lookup_order(order_id='ORD-78234')", type: "system" },
  { id: 6, sender: "ai_bot", content: "I found your order. It was shipped on December 10th via Express shipping, and the tracking shows it's currently in transit at the local distribution center. The expected delivery is tomorrow, December 16th. Would you like me to send you the tracking link?", type: "agent" },
  { id: 7, sender: "customer", content: "Yes please, and can you also make sure someone needs to sign for it? I don't want it left at the door.", type: "customer" },
  { id: 8, sender: "ai_bot", content: "Absolutely! I've noted the signature requirement on your delivery. You'll receive the tracking link via email shortly. Is there anything else I can help you with today?", type: "agent" },
  { id: 9, sender: "customer", content: "No, that's all. Thank you so much!", type: "customer" },
  { id: 10, sender: "ai_bot", content: "You're welcome, Sarah! Have a wonderful day. Goodbye!", type: "agent" },
  { id: 11, sender: "system", content: "Call ended — Duration: 4:32", type: "system" },
];

export default function ConversationDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/dashboard/conversations" className="p-2 rounded-xl hover:bg-white/5 transition-all-200">
          <ArrowLeft className="w-5 h-5 text-[var(--muted)]" />
        </Link>
        <div className="flex-1">
          <h1 className="text-xl font-bold">Conversation {id}</h1>
          <p className="text-sm text-[var(--foreground-muted)]">Sarah Johnson • +1-555-0101</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm"><TicketIcon className="w-4 h-4 mr-1" /> Create Ticket</Button>
          <Button variant="danger" size="sm"><AlertTriangle className="w-4 h-4 mr-1" /> Escalate</Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Transcript */}
        <div className="lg:col-span-2">
          <Card title="Conversation Transcript" noPadding>
            <div className="px-6 pt-6 pb-2"><h3 className="text-lg font-semibold">Conversation Transcript</h3></div>
            <div className="p-6 space-y-4 max-h-[600px] overflow-y-auto">
              {mockMessages.map((m) => {
                if (m.type === "system") {
                  return (
                    <div key={m.id} className="text-center">
                      <span className="text-xs text-[var(--foreground-muted)] bg-white/5 px-3 py-1 rounded-full">{m.content}</span>
                    </div>
                  );
                }
                const isAgent = m.type === "agent";
                return (
                  <div key={m.id} className={`flex ${isAgent ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[75%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                      isAgent
                        ? "bg-emerald-500/15 border border-emerald-500/20 text-[var(--foreground)] rounded-br-md"
                        : "bg-blue-500/15 border border-blue-500/20 text-[var(--foreground)] rounded-bl-md"
                    }`}>
                      <p className="text-xs font-medium mb-1 opacity-60">{isAgent ? "🤖 Ava (AI)" : "👤 Sarah Johnson"}</p>
                      {m.content}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        </div>

        {/* Metadata */}
        <div className="space-y-4">
          <Card title="Call Details">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-[var(--foreground-muted)]">Status</span>
                <Badge variant="success" dot>Completed</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-[var(--foreground-muted)]">Channel</span>
                <div className="flex items-center gap-1.5"><Phone className="w-3.5 h-3.5 text-[var(--primary)]" /><span className="text-sm">Voice</span></div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-[var(--foreground-muted)]">Duration</span>
                <div className="flex items-center gap-1.5"><Clock className="w-3.5 h-3.5 text-[var(--muted)]" /><span className="text-sm">4:32</span></div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-[var(--foreground-muted)]">Direction</span>
                <span className="text-sm">Inbound</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-[var(--foreground-muted)]">Language</span>
                <span className="text-sm">English (US)</span>
              </div>
            </div>
          </Card>

          <Card title="AI Performance">
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-[var(--foreground-muted)]">AI Confidence</span>
                  <span className="font-semibold text-[var(--accent)]">94%</span>
                </div>
                <div className="w-full h-2 rounded-full bg-white/10 overflow-hidden">
                  <div className="h-full rounded-full bg-gradient-to-r from-blue-500 to-emerald-500" style={{ width: "94%" }} />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-[var(--foreground-muted)]">Sentiment</span>
                  <span className="font-semibold text-[var(--accent)]">+0.82 😊</span>
                </div>
                <div className="w-full h-2 rounded-full bg-white/10 overflow-hidden">
                  <div className="h-full rounded-full bg-[var(--accent)]" style={{ width: "91%" }} />
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-[var(--foreground-muted)]">Intent</span>
                <Badge variant="info">Order Tracking</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-[var(--foreground-muted)]">Handled by</span>
                <div className="flex items-center gap-1.5"><BrainCircuit className="w-3.5 h-3.5 text-[var(--primary)]" /><span className="text-sm">AI Only</span></div>
              </div>
            </div>
          </Card>

          <Card title="Customer">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-pink-500 to-orange-500 flex items-center justify-center text-sm font-bold">SJ</div>
              <div>
                <p className="text-sm font-semibold">Sarah Johnson</p>
                <p className="text-xs text-[var(--foreground-muted)]">Premium Customer</p>
              </div>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-[var(--foreground-muted)]">Phone</span><span>+1-555-0101</span></div>
              <div className="flex justify-between"><span className="text-[var(--foreground-muted)]">Email</span><span>sarah.j@email.com</span></div>
              <div className="flex justify-between"><span className="text-[var(--foreground-muted)]">Total Calls</span><span>12</span></div>
              <div className="flex justify-between"><span className="text-[var(--foreground-muted)]">Avg Sentiment</span><span className="text-[var(--accent)]">+0.76</span></div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
