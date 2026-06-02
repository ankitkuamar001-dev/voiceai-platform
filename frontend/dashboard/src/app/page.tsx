"use client";
import Link from "next/link";
import { Phone, Brain, BarChart3, Shield, Zap, Globe } from "lucide-react";
import { Button } from "@/components/ui/button";

const features = [
  { icon: <Phone className="w-6 h-6" />, title: "Voice AI Agent", desc: "Natural conversations powered by GPT-4o with real-time STT/TTS pipeline" },
  { icon: <Brain className="w-6 h-6" />, title: "Intelligent RAG", desc: "Knowledge base retrieval with semantic search for accurate answers" },
  { icon: <BarChart3 className="w-6 h-6" />, title: "Live Analytics", desc: "Real-time dashboards with sentiment tracking and performance metrics" },
  { icon: <Shield className="w-6 h-6" />, title: "Enterprise Security", desc: "Multi-tenant isolation, RBAC, encrypted recordings, GDPR compliant" },
  { icon: <Zap className="w-6 h-6" />, title: "Auto-Escalation", desc: "Intelligent handoff to human agents based on sentiment and confidence" },
  { icon: <Globe className="w-6 h-6" />, title: "Multi-Channel", desc: "Phone, WhatsApp, web chat — unified experience across all channels" },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen relative overflow-hidden">
      {/* Background effects */}
      <div className="absolute top-0 left-1/4 w-[600px] h-[600px] rounded-full bg-blue-500/5 blur-[120px]" />
      <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] rounded-full bg-emerald-500/5 blur-[120px]" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full bg-purple-500/3 blur-[150px]" />

      {/* Nav */}
      <nav className="relative z-10 flex items-center justify-between px-8 py-6 max-w-7xl mx-auto">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-emerald-500 flex items-center justify-center">
            <Phone className="w-5 h-5 text-white" />
          </div>
          <span className="text-xl font-bold gradient-text">VoiceAI</span>
        </div>
        <Link href="/login">
          <Button size="md">Sign In</Button>
        </Link>
      </nav>

      {/* Hero */}
      <section className="relative z-10 text-center px-8 pt-24 pb-16 max-w-5xl mx-auto">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-blue-500/30 bg-blue-500/10 text-blue-400 text-sm mb-8">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-400"></span>
          </span>
          AI-Powered Voice Support Platform
        </div>
        <h1 className="text-5xl sm:text-7xl font-bold leading-tight mb-6">
          Customer Support{" "}
          <span className="gradient-text">That Speaks</span>
          <br />
          For Itself
        </h1>
        <p className="text-xl text-[var(--foreground-muted)] max-w-2xl mx-auto mb-10 leading-relaxed">
          Deploy intelligent voice agents that handle thousands of calls simultaneously.
          Natural conversations, instant resolution, zero wait times.
        </p>
        <div className="flex items-center justify-center gap-4">
          <Link href="/login">
            <Button size="lg" className="text-base px-8">
              Launch Dashboard →
            </Button>
          </Link>
          <Button variant="secondary" size="lg" className="text-base px-8">
            Watch Demo
          </Button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-8 mt-20 max-w-2xl mx-auto">
          {[
            { value: "99.9%", label: "Uptime SLA" },
            { value: "<300ms", label: "Response Latency" },
            { value: "10K+", label: "Concurrent Calls" },
          ].map((s) => (
            <div key={s.label}>
              <p className="text-3xl font-bold gradient-text">{s.value}</p>
              <p className="text-sm text-[var(--foreground-muted)] mt-1">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="relative z-10 px-8 py-20 max-w-6xl mx-auto">
        <h2 className="text-3xl font-bold text-center mb-12">Enterprise-Grade Features</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((f) => (
            <div key={f.title} className="glass glass-hover transition-all-200 p-6 group">
              <div className="w-12 h-12 rounded-xl bg-blue-500/10 flex items-center justify-center text-blue-400 mb-4 group-hover:bg-blue-500/20 transition-all-200">
                {f.icon}
              </div>
              <h3 className="text-lg font-semibold mb-2">{f.title}</h3>
              <p className="text-sm text-[var(--foreground-muted)] leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="relative z-10 px-8 py-20 text-center">
        <div className="max-w-3xl mx-auto glass p-12">
          <h2 className="text-3xl font-bold mb-4">Ready to Transform Your Support?</h2>
          <p className="text-[var(--foreground-muted)] mb-8">Start with a free trial. No credit card required.</p>
          <Link href="/login">
            <Button size="lg" className="text-base px-10">Get Started Free →</Button>
          </Link>
        </div>
      </section>
    </div>
  );
}
