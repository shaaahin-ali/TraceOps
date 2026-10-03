"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Plus, AlertTriangle, Activity, CheckCircle, Search, Zap,
  ArrowRight, BarChart2, Clock, LogOut
} from "lucide-react";
import { api } from "@/lib/api";

function SeverityBadge({ severity }: { severity: string }) {
  const cls = severity === "CRITICAL" ? "badge-critical" : severity === "HIGH" ? "badge-high"
    : severity === "MEDIUM" ? "badge-medium" : "badge-low";
  return <span className={`badge ${cls}`}>{severity}</span>;
}

function StatusBadge({ status }: { status: string }) {
  const cls = status === "INVESTIGATING" ? "badge-investigating"
    : status === "RESOLVED" ? "badge-resolved"
    : "badge-open";
  return <span className={`badge ${cls}`}>{status}</span>;
}

export default function Dashboard() {
  const router = useRouter();
  const [incidents, setIncidents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    title: "", description: "", service: "payment-api",
    severity: "HIGH", incident_time: ""
  });
  const [user, setUser] = useState<any>(null);

  useEffect(() => {
    const u = localStorage.getItem("rt_user");
    if (u) setUser(JSON.parse(u));
    loadIncidents();
  }, []);

  async function loadIncidents() {
    try {
      const data = await api.getIncidents();
      setIncidents(data);
    } catch (e) {
      router.push("/login");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    try {
      const inc = await api.createIncident({
        ...form,
        incident_time: form.incident_time || new Date().toISOString(),
      });
      await api.startInvestigation(inc.id);
      router.push(`/investigation/${inc.id}`);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setCreating(false);
    }
  }

  function handleLogout() {
    localStorage.clear();
    router.push("/login");
  }

  // Stats
  const total = incidents.length;
  const investigating = incidents.filter(i => i.status === "INVESTIGATING").length;
  const resolved = incidents.filter(i => i.status === "RESOLVED").length;
  const highSeverity = incidents.filter(i => ["HIGH", "CRITICAL"].includes(i.severity)).length;

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-primary)" }}>
      {/* Nav */}
      <nav className="border-b" style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}>
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center"
              style={{ background: "rgba(59,130,246,0.2)", border: "1px solid rgba(59,130,246,0.4)" }}>
              <Zap className="w-3.5 h-3.5 text-blue-400" />
            </div>
            <span className="font-bold text-gradient">RootTrace</span>
            <span className="text-xs ml-2 px-2 py-0.5 rounded font-mono"
              style={{ background: "rgba(59,130,246,0.1)", color: "var(--accent-blue)", border: "1px solid rgba(59,130,246,0.2)" }}>
              MVP
            </span>
          </div>
          <div className="flex items-center gap-4">
            {user && (
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                {user.name} · <span style={{ color: "var(--accent-blue)" }}>{user.role}</span>
              </span>
            )}
            <button onClick={() => router.push("/evaluation")} className="flex items-center gap-1.5 text-xs transition-colors"
              style={{ color: "var(--text-muted)" }}
              onMouseOver={e => (e.currentTarget.style.color = "var(--accent-blue)")}
              onMouseOut={e => (e.currentTarget.style.color = "var(--text-muted)")}>
              <BarChart2 className="w-3.5 h-3.5" /> Eval
            </button>
            <button onClick={handleLogout} className="flex items-center gap-1.5 text-xs transition-colors"
              style={{ color: "var(--text-muted)" }}>
              <LogOut className="w-3.5 h-3.5" /> Logout
            </button>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold mb-1" style={{ color: "var(--text-primary)" }}>
              Incident Dashboard
            </h1>
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
              Evidence-driven AI investigation platform
            </p>
          </div>
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all"
            style={{
              background: "linear-gradient(135deg, #1d4ed8, #3b82f6)",
              color: "white",
            }}
          >
            <Plus className="w-4 h-4" /> New Investigation
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {[
            { label: "Total Incidents", value: total, icon: BarChart2, color: "#3b82f6" },
            { label: "Investigating", value: investigating, icon: Activity, color: "#f59e0b" },
            { label: "High Severity", value: highSeverity, icon: AlertTriangle, color: "#ef4444" },
            { label: "Resolved", value: resolved, icon: CheckCircle, color: "#22c55e" },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="glass-card p-5">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-medium uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>{label}</span>
                <Icon className="w-4 h-4" style={{ color }} />
              </div>
              <div className="text-3xl font-bold" style={{ color }}>{value}</div>
            </div>
          ))}
        </div>

        {/* Create Form */}
        {showCreate && (
          <div className="glass-card p-6 mb-6 animate-fade-in glow-blue">
            <h2 className="font-bold mb-4" style={{ color: "var(--text-primary)" }}>
              🔍 Start New Investigation
            </h2>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="md:col-span-2">
                  <label className="block text-xs font-medium mb-1.5" style={{ color: "var(--text-muted)" }}>Incident Title</label>
                  <input
                    value={form.title}
                    onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                    className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                    style={{ background: "rgba(30,45,74,0.5)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
                    placeholder="Payment API latency increased 300% after latest deployment"
                    required
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-xs font-medium mb-1.5" style={{ color: "var(--text-muted)" }}>Description</label>
                  <textarea
                    value={form.description}
                    onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                    className="w-full px-3 py-2 rounded-lg text-sm outline-none resize-none"
                    style={{ background: "rgba(30,45,74,0.5)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
                    placeholder="Describe the symptoms, when they started, what changed..."
                    rows={3}
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1.5" style={{ color: "var(--text-muted)" }}>Service</label>
                  <select
                    value={form.service}
                    onChange={e => setForm(f => ({ ...f, service: e.target.value }))}
                    className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                    style={{ background: "rgba(30,45,74,0.5)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
                  >
                    <option value="payment-api">payment-api</option>
                    <option value="fraud-service">fraud-service</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1.5" style={{ color: "var(--text-muted)" }}>Severity</label>
                  <select
                    value={form.severity}
                    onChange={e => setForm(f => ({ ...f, severity: e.target.value }))}
                    className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                    style={{ background: "rgba(30,45,74,0.5)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
                  >
                    {["CRITICAL", "HIGH", "MEDIUM", "LOW"].map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1.5" style={{ color: "var(--text-muted)" }}>Incident Time (UTC)</label>
                  <input
                    type="datetime-local"
                    value={form.incident_time}
                    onChange={e => setForm(f => ({ ...f, incident_time: e.target.value }))}
                    className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                    style={{ background: "rgba(30,45,74,0.5)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
                  />
                </div>
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="submit"
                  disabled={creating}
                  className="flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-semibold"
                  style={{ background: "linear-gradient(135deg, #1d4ed8, #3b82f6)", color: "white" }}
                >
                  {creating ? (
                    <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Starting...</>
                  ) : (
                    <><Zap className="w-4 h-4" /> Start Investigation</>
                  )}
                </button>
                <button type="button" onClick={() => setShowCreate(false)}
                  className="px-4 py-2.5 rounded-xl text-sm" style={{ color: "var(--text-muted)", border: "1px solid var(--border)" }}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Incidents List */}
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wider mb-4" style={{ color: "var(--text-muted)" }}>
            Recent Incidents
          </h2>
          {loading ? (
            <div className="glass-card p-6 text-center" style={{ color: "var(--text-muted)" }}>Loading...</div>
          ) : incidents.length === 0 ? (
            <div className="glass-card p-12 text-center">
              <Search className="w-8 h-8 mx-auto mb-3" style={{ color: "var(--text-muted)" }} />
              <p style={{ color: "var(--text-muted)" }}>No incidents yet. Create your first investigation.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {incidents.map(inc => (
                <div
                  key={inc.id}
                  onClick={() => router.push(`/investigation/${inc.id}`)}
                  className="glass-card p-5 cursor-pointer transition-all group"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1.5">
                        <SeverityBadge severity={inc.severity} />
                        <StatusBadge status={inc.status} />
                        <span className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>{inc.service}</span>
                      </div>
                      <h3 className="font-medium text-sm mb-1 group-hover:text-blue-400 transition-colors"
                        style={{ color: "var(--text-primary)" }}>
                        {inc.title}
                      </h3>
                      <div className="flex items-center gap-3 text-xs" style={{ color: "var(--text-muted)" }}>
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {new Date(inc.created_at).toLocaleDateString()}
                        </span>
                        {inc.confidence_score && (
                          <span style={{ color: "#22c55e" }}>
                            Confidence: {inc.confidence_score.toFixed(0)}/100
                          </span>
                        )}
                      </div>
                    </div>
                    <ArrowRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity ml-4"
                      style={{ color: "var(--accent-blue)" }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
