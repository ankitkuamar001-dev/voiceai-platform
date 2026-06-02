"use client";
import { useState } from "react";
import { Mic, MicOff, PhoneOff, Phone } from "lucide-react";
import { cn } from "@/lib/utils";

export function VoiceWidget() {
  const [active, setActive] = useState(false);
  const [muted, setMuted] = useState(false);

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {active ? (
        <div className="glass-strong p-6 w-72 space-y-4 shadow-2xl shadow-blue-500/10">
          {/* Status */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-400"></span>
              </span>
              <span className="text-sm font-medium text-emerald-400">Connected</span>
            </div>
            <span className="text-xs text-[var(--foreground-muted)]">00:42</span>
          </div>

          {/* Waveform */}
          <div className="flex items-center justify-center gap-1 h-10">
            {[...Array(12)].map((_, i) => (
              <div key={i} className={cn("w-1 rounded-full bg-[var(--primary)]", muted ? "h-1" : "waveform-bar")}
                style={muted ? {} : { animationDelay: `${i * 0.08}s`, animationDuration: `${0.6 + ((i * 3) % 4) * 0.1}s` }} />
            ))}
          </div>

          {/* Controls */}
          <div className="flex items-center justify-center gap-4">
            <button onClick={() => setMuted(!muted)}
              className={cn("w-12 h-12 rounded-full flex items-center justify-center transition-all-200",
                muted ? "bg-amber-500/20 text-amber-400" : "bg-white/10 text-[var(--foreground)] hover:bg-white/20")}>
              {muted ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
            </button>
            <button onClick={() => setActive(false)}
              className="w-14 h-14 rounded-full bg-[var(--danger)] flex items-center justify-center text-white shadow-lg shadow-rose-500/25 hover:bg-rose-600 transition-all-200">
              <PhoneOff className="w-6 h-6" />
            </button>
          </div>
        </div>
      ) : (
        <button onClick={() => setActive(true)}
          className="relative w-16 h-16 rounded-full bg-gradient-to-br from-blue-500 to-emerald-500 flex items-center justify-center text-white shadow-xl shadow-blue-500/30 hover:shadow-blue-500/50 transition-all-200 hover:scale-105">
          <Phone className="w-7 h-7" />
          <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-emerald-400 border-2 border-[var(--background)]" />
        </button>
      )}
    </div>
  );
}
