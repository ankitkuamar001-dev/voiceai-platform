"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Phone } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuthStore } from "@/lib/store";
import { api } from "@/lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const login = useAuthStore((s) => s.login);
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await api.post<{
        access_token: string;
        refresh_token: string;
        user: { id: string; email: string; full_name: string; user_type: string; org_id: string };
      }>("/api/v1/auth/login", { email, password });
      login(res.user, res.access_token, res.refresh_token);
      router.push("/dashboard");
    } catch (err) {
      // For demo, allow a bypass
      if (email === "admin@voiceai.demo" && password === "admin123") {
        login(
          { id: "demo-user", email, full_name: "Admin User", user_type: "admin", org_id: "demo-org" },
          "demo-token",
          "demo-refresh"
        );
        router.push("/dashboard");
        return;
      }
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden px-4">
      {/* Background effects */}
      <div className="absolute top-1/4 left-1/3 w-[500px] h-[500px] rounded-full bg-blue-500/8 blur-[120px]" />
      <div className="absolute bottom-1/4 right-1/3 w-[400px] h-[400px] rounded-full bg-purple-500/8 blur-[120px]" />

      <div className="w-full max-w-md relative z-10">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500 to-emerald-500 items-center justify-center mb-4">
            <Phone className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-2xl font-bold">Welcome to <span className="gradient-text">VoiceAI</span></h1>
          <p className="text-[var(--foreground-muted)] mt-2 text-sm">Sign in to your dashboard</p>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="glass p-8 space-y-5">
          <Input
            label="Email Address"
            type="email"
            placeholder="admin@voiceai.demo"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <Input
            label="Password"
            type="password"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {error && (
            <div className="text-sm text-[var(--danger)] bg-rose-500/10 p-3 rounded-lg border border-rose-500/20">{error}</div>
          )}
          <Button type="submit" className="w-full" loading={loading}>
            Sign In
          </Button>

          {/* Demo hint */}
          <div className="text-center pt-2">
            <p className="text-xs text-[var(--foreground-muted)]">
              Demo credentials: <code className="text-[var(--primary)]">admin@voiceai.demo</code> / <code className="text-[var(--primary)]">admin123</code>
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}
