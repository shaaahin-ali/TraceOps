"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, Zap, Shield, Search } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Login failed");
      }
      const data = await res.json();
      localStorage.setItem("rt_token", data.access_token);
      localStorage.setItem("rt_user", JSON.stringify({ name: data.name, email: data.email, role: data.role }));
      router.replace("/dashboard");
    } catch (err: any) {
      setError(err.message || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex" style={{ background: "var(--bg-primary)" }}>
      {/* Left panel */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-center p-16 relative overflow-hidden">
        <div className="absolute inset-0" style={{
          background: "radial-gradient(ellipse at 20% 50%, rgba(59,130,246,0.08) 0%, transparent 60%), radial-gradient(ellipse at 80% 20%, rgba(168,85,247,0.06) 0%, transparent 50%)"
        }} />
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-12">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: "rgba(59,130,246,0.2)", border: "1px solid rgba(59,130,246,0.4)" }}>
              <Zap className="w-5 h-5 text-blue-400" />
            </div>
            <span className="text-xl font-bold text-gradient">RootTrace</span>
          </div>

          <h1 className="text-4xl font-bold mb-6 leading-tight" style={{ color: "var(--text-primary)" }}>
            Agentic AI for<br />
            <span className="text-gradient">Evidence-Driven</span><br />
            Incident Investigation
          </h1>

          <p className="text-lg mb-12" style={{ color: "var(--text-secondary)" }}>
            Stop guessing. Let the evidence speak.
          </p>

          <div className="space-y-4">
            {[
              { icon: Search, text: "Searches Git, logs, metrics, and deployments" },
              { icon: Shield, text: "Generates competing hypotheses — tests each one" },
              { icon: Zap, text: "Evidence confidence score, never invented answers" },
            ].map(({ icon: Icon, text }) => (
              <div key={text} className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ background: "rgba(59,130,246,0.15)", border: "1px solid rgba(59,130,246,0.2)" }}>
                  <Icon className="w-4 h-4 text-blue-400" />
                </div>
                <span style={{ color: "var(--text-secondary)" }}>{text}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right panel — login form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <div className="glass-card p-8 glow-blue">
            <div className="flex items-center gap-2 mb-8 lg:hidden">
              <Zap className="w-6 h-6 text-blue-400" />
              <span className="text-lg font-bold text-gradient">RootTrace</span>
            </div>

            <h2 className="text-2xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>Sign in</h2>
            <p className="mb-8 text-sm" style={{ color: "var(--text-secondary)" }}>
              Enter your credentials to access the investigation platform
            </p>

            {error && (
              <div className="flex items-center gap-2 p-3 rounded-lg mb-6 animate-fade-in"
                style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)" }}>
                <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                <span className="text-sm text-red-400">{error}</span>
              </div>
            )}

            <form onSubmit={handleLogin} className="space-y-5">
              <div>
                <label className="block text-sm font-medium mb-1.5" style={{ color: "var(--text-secondary)" }}>Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg text-sm outline-none transition-all"
                  style={{
                    background: "rgba(30,45,74,0.5)",
                    border: "1px solid var(--border)",
                    color: "var(--text-primary)",
                  }}
                  onFocus={e => e.target.style.borderColor = "var(--accent-blue)"}
                  onBlur={e => e.target.style.borderColor = "var(--border)"}
                  placeholder="sre@roottrace.dev"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1.5" style={{ color: "var(--text-secondary)" }}>Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg text-sm outline-none transition-all"
                  style={{
                    background: "rgba(30,45,74,0.5)",
                    border: "1px solid var(--border)",
                    color: "var(--text-primary)",
                  }}
                  onFocus={e => e.target.style.borderColor = "var(--accent-blue)"}
                  onBlur={e => e.target.style.borderColor = "var(--border)"}
                  placeholder="••••••••"
                  required
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 rounded-lg font-semibold text-sm transition-all duration-200 mt-2"
                style={{
                  background: loading ? "rgba(59,130,246,0.5)" : "linear-gradient(135deg, #2563eb, #3b82f6)",
                  color: "white",
                  cursor: loading ? "not-allowed" : "pointer",
                }}
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Signing in...
                  </span>
                ) : "Sign In"}
              </button>
            </form>

            <div className="mt-8 p-4 rounded-lg" style={{ background: "rgba(30,45,74,0.4)", border: "1px solid var(--border)" }}>
              <p className="text-xs font-medium mb-2" style={{ color: "var(--text-muted)" }}>TEST ACCOUNTS</p>
              <div className="space-y-1 font-mono text-xs" style={{ color: "var(--text-secondary)" }}>
                <div>sre@roottrace.dev / sre123 <span className="text-blue-400">(SRE)</span></div>
                <div>dev@roottrace.dev / dev123 <span style={{ color: "var(--text-muted)" }}>(USER)</span></div>
                <div>admin@roottrace.dev / admin123 <span className="text-purple-400">(ADMIN)</span></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
