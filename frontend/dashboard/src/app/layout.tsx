import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VoiceAI — Enterprise AI Voice Support Platform",
  description: "Enterprise-grade AI voice customer support system with real-time conversations, intelligent routing, and advanced analytics.",
  keywords: "AI voice support, customer support, voice AI, call center AI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[var(--background)] text-[var(--foreground)] antialiased">
        {children}
      </body>
    </html>
  );
}
