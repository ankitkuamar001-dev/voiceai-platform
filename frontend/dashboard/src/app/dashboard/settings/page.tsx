"use client";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

export default function SettingsPage() {
  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-[var(--foreground-muted)] text-sm mt-1">Manage your organization and AI agent configuration</p>
      </div>

      <Card title="Organization">
        <div className="space-y-4 max-w-lg">
          <Input label="Organization Name" defaultValue="VoiceAI Demo" />
          <Input label="Domain" defaultValue="voiceai.demo" />
          <div className="flex items-center justify-between">
            <span className="text-sm text-[var(--foreground-muted)]">Plan</span>
            <Badge variant="purple">Enterprise</Badge>
          </div>
          <Button>Save Changes</Button>
        </div>
      </Card>

      <Card title="AI Agent Configuration">
        <div className="space-y-4 max-w-lg">
          <Input label="Agent Name" defaultValue="Ava" />
          <Input label="Voice" defaultValue="Professional Female (Sonic)" />
          <Input label="Default Language" defaultValue="en-US" />
          <div>
            <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-1.5">System Prompt</label>
            <textarea rows={4} defaultValue="You are a professional customer support agent..."
              className="w-full px-4 py-2.5 rounded-xl text-sm bg-[var(--input-bg)] border border-[var(--border)] text-[var(--foreground)] focus:outline-none focus:border-[var(--primary)] transition-all-200 resize-none" />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-[var(--foreground-muted)]">Escalation Threshold</span>
            <span className="text-sm">Confidence &lt; 70%</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-[var(--foreground-muted)]">Max Turn Count</span>
            <span className="text-sm">20 turns</span>
          </div>
          <Button>Update AI Config</Button>
        </div>
      </Card>

      <Card title="Integrations">
        <div className="space-y-3">
          {[
            { name: "Twilio", status: "connected", desc: "Phone & SMS" },
            { name: "LiveKit", status: "connected", desc: "Voice pipeline" },
            { name: "OpenAI", status: "connected", desc: "GPT-4o LLM" },
            { name: "Deepgram", status: "connected", desc: "Speech-to-text" },
            { name: "Pinecone", status: "connected", desc: "Vector database" },
            { name: "WhatsApp", status: "disconnected", desc: "Not configured" },
          ].map((i) => (
            <div key={i.name} className="flex items-center justify-between py-2">
              <div>
                <p className="text-sm font-medium">{i.name}</p>
                <p className="text-xs text-[var(--foreground-muted)]">{i.desc}</p>
              </div>
              <Badge variant={i.status === "connected" ? "success" : "default"} dot>{i.status}</Badge>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
