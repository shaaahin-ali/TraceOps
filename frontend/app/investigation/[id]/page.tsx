"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import {
  ArrowLeft, RefreshCw, CheckCircle2, Clock, AlertTriangle,
  Database, GitCommit, FileText, BarChart2, Search, Shield, Zap
} from "lucide-react";
import { api } from "@/lib/api";

const EVENT_ICONS: Record<string, any> = {
  INCIDENT_RECEIVED: Zap,
  INCIDENT_CLASSIFIED: Search,
  PLAN_CREATED: FileText,
  TOOL_CALLED: Database,
  TOOL_RESULT: CheckCircle2,
  EVIDENCE_FOUND: Search,
  HYPOTHESES_GENERATED: BarChart2,
  HYPOTHESIS_TESTED: BarChart2,
  VALIDATION_COMPLETED: CheckCircle2,
  ROOT_CAUSE_RANKED: BarChart2,
  RECOMMENDATION_GENERATED: Shield,
  HUMAN_APPROVAL_REQUIRED: AlertTriangle,
  HUMAN_APPROVED: CheckCircle2,
  REPORT_GENERATED: FileText,
  INVESTIGATION_COMPLETED: CheckCircle2,
  INVESTIGATION_FAILED: AlertTriangle,
};

function ConfidenceBar({ score }: { score: number }) {
  const level = score >= 80 ? "strong" : score >= 60 ? "moderate" : "weak";
  const color = score >= 80 ? "#22c55e" : score >= 60 ? "#3b82f6" : "#f59e0b";
  return (
    <div className="flex items-center gap-3">
      <div className="confidence-bar flex-1">
        <div
          className="confidence-fill"
          style={{ width: `${score}%`, background: color }}
        />
      </div>
      <span className="font-mono text-sm font-bold" style={{ color }}>{score.toFixed(0)}/100</span>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const cls = status.toLowerCase().includes("investigat") ? "badge-investigating"
    : status === "RESOLVED" ? "badge-resolved"
    : status === "OPEN" ? "badge-open"
    : "badge-investigating";
  return <span className={`badge ${cls}`}>{status}</span>;
}

function HypothesisBadge({ status }: { status: string }) {
  if (!status) return null;
  const cls = status === "SUPPORTED" ? "badge-supported"
    : status === "PARTIALLY_SUPPORTED" ? "badge-partial"
    : "badge-unsupported";
  return <span className={`badge ${cls}`}>{status.replace("_", " ")}</span>;
}

function RiskBadge({ level }: { level: string }) {
  const cls = level === "HIGH" ? "badge-critical" : level === "MEDIUM" ? "badge-medium" : "badge-low";
  return <span className={`badge ${cls}`}>{level} RISK</span>;
}

export default function InvestigationPage() {
  const router = useRouter();
  const params = useParams();
  const id = params.id as string;

  const [incident, setIncident] = useState<any>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [hypotheses, setHypotheses] = useState<any[]>([]);
  const [evidence, setEvidence] = useState<any[]>([]);
  const [recommendations, setRecommendations] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState("timeline");
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(false);
  const [approving, setApproving] = useState<string | null>(null);

  async function loadAll() {
    try {
      const [inc, evts, hyps, evid, recs] = await Promise.all([
        api.getIncident(id),
        api.getEvents(id),
        api.getHypotheses(id),
        api.getEvidence(id),
        api.getRecommendations(id),
      ]);
      setIncident(inc);
      setEvents(evts);
      setHypotheses(hyps);
      setEvidence(evid);
      setRecommendations(recs);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, [id]);

  // Poll while investigating
  useEffect(() => {
    if (!incident) return;
    if (incident.status === "INVESTIGATING") {
      const interval = setInterval(loadAll, 3000);
      return () => clearInterval(interval);
    }
  }, [incident?.status]);

  async function handleApprove(recId: string) {
    setApproving(recId);
    try {
      await api.approve(recId);
      await loadAll();
    } finally {
      setApproving(null);
    }
  }

  async function handleReject(recId: string) {
    setApproving(recId);
    try {
      await api.reject(recId);
      await loadAll();
    } finally {
      setApproving(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen" style={{ background: "var(--bg-primary)" }}>
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <span style={{ color: "var(--text-secondary)" }}>Loading investigation...</span>
        </div>
      </div>
    );
  }

  const isInvestigating = incident?.status === "INVESTIGATING";

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-primary)" }}>
      {/* Header */}
      <div className="border-b" style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}>
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center gap-4 mb-4">
            <button onClick={() => router.push("/dashboard")} className="flex items-center gap-1.5 text-sm transition-colors"
              style={{ color: "var(--text-muted)" }}
              onMouseOver={e => (e.currentTarget.style.color = "var(--text-primary)")}
              onMouseOut={e => (e.currentTarget.style.color = "var(--text-muted)")}>
              <ArrowLeft className="w-4 h-4" /> Dashboard
            </button>
          </div>
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
                  {incident?.title}
                </h1>
                {incident && <StatusBadge status={incident.status} />}
              </div>
              <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                Service: <span className="font-mono text-blue-400">{incident?.service}</span>
                {incident?.confidence_score && (
                  <span className="ml-4">Confidence: <span className="font-bold" style={{ color: "#22c55e" }}>{incident.confidence_score.toFixed(0)}/100</span></span>
                )}
              </p>
            </div>
            {isInvestigating && (
              <div className="flex items-center gap-2 text-sm text-blue-400">
                <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
                Investigating...
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b" style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}>
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex gap-0">
            {[
              { id: "timeline", label: "Timeline", count: events.length },
              { id: "hypotheses", label: "Hypotheses", count: hypotheses.length },
              { id: "evidence", label: "Evidence", count: evidence.length },
              { id: "recommendations", label: "Recommendations", count: recommendations.length },
              { id: "report", label: "Report" },
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className="px-4 py-3 text-sm font-medium border-b-2 transition-colors"
                style={{
                  borderColor: activeTab === tab.id ? "var(--accent-blue)" : "transparent",
                  color: activeTab === tab.id ? "var(--accent-blue)" : "var(--text-muted)",
                }}
              >
                {tab.label}
                {tab.count !== undefined && (
                  <span className="ml-1.5 px-1.5 py-0.5 rounded text-xs"
                    style={{ background: "rgba(59,130,246,0.15)", color: "var(--accent-blue)" }}>
                    {tab.count}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6">
        {/* Timeline Tab */}
        {activeTab === "timeline" && (
          <div className="max-w-2xl">
            <h2 className="text-sm font-semibold uppercase tracking-wider mb-4" style={{ color: "var(--text-muted)" }}>
              Investigation Timeline
            </h2>
            {events.length === 0 ? (
              <div className="glass-card p-6 text-center" style={{ color: "var(--text-muted)" }}>
                {isInvestigating ? "Waiting for first event..." : "No events yet"}
              </div>
            ) : (
              <div className="space-y-4">
                {events.map((event, i) => {
                  const Icon = EVENT_ICONS[event.event_type] || Clock;
                  const isLast = i === events.length - 1;
                  return (
                    <div key={event.id} className="timeline-item animate-fade-in">
                      <div className={`timeline-dot ${isInvestigating && isLast ? "active" : "completed"}`}>
                        <Icon className="w-2.5 h-2.5 text-white" />
                      </div>
                      <div className="glass-card p-4 ml-2">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-mono font-medium" style={{ color: "var(--accent-blue)" }}>
                            {event.event_type}
                          </span>
                          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                            {new Date(event.timestamp).toLocaleTimeString()}
                          </span>
                        </div>
                        {event.summary && (
                          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{event.summary}</p>
                        )}
                        {event.tool_name && (
                          <span className="text-xs font-mono mt-1 inline-block px-2 py-0.5 rounded"
                            style={{ background: "rgba(59,130,246,0.1)", color: "var(--accent-blue)" }}>
                            {event.tool_name}
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
                {isInvestigating && (
                  <div className="timeline-item">
                    <div className="timeline-dot active">
                      <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
                    </div>
                    <div className="p-4 ml-2 text-sm" style={{ color: "var(--text-muted)" }}>
                      <span className="cursor-blink">Agent working</span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Hypotheses Tab */}
        {activeTab === "hypotheses" && (
          <div className="space-y-4">
            <h2 className="text-sm font-semibold uppercase tracking-wider mb-4" style={{ color: "var(--text-muted)" }}>
              Root Cause Hypotheses
            </h2>
            {hypotheses.length === 0 ? (
              <div className="glass-card p-6 text-center" style={{ color: "var(--text-muted)" }}>
                Hypotheses will appear here once generated
              </div>
            ) : (
              hypotheses.map((h, i) => (
                <div key={h.id} className={`glass-card p-6 animate-fade-in ${h.rank === 1 ? "active-investigation-border" : ""}`}>
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-lg font-bold" style={{ color: "var(--accent-blue)" }}>{h.hypothesis_id}</span>
                      {h.rank === 1 && <span className="badge badge-supported text-xs">TOP CANDIDATE</span>}
                    </div>
                    <div className="flex items-center gap-2">
                      <HypothesisBadge status={h.status} />
                    </div>
                  </div>
                  <p className="font-medium mb-4" style={{ color: "var(--text-primary)" }}>{h.description}</p>
                  {h.confidence_score != null && (
                    <ConfidenceBar score={h.confidence_score} />
                  )}
                  {h.missing_evidence?.length > 0 && (
                    <div className="mt-3 text-xs" style={{ color: "var(--text-muted)" }}>
                      Missing: {h.missing_evidence.join(", ")}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {/* Evidence Tab */}
        {activeTab === "evidence" && (
          <div className="space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-wider mb-4" style={{ color: "var(--text-muted)" }}>
              Collected Evidence ({evidence.length} items)
            </h2>
            {evidence.map((ev, i) => (
              <div key={ev.id} className="glass-card p-4 animate-fade-in">
                <div className="flex items-center gap-2 mb-2">
                  <span className="badge badge-investigating text-xs">{ev.source_type}</span>
                  {ev.source_id && (
                    <span className="font-mono text-xs" style={{ color: "var(--text-muted)" }}>{ev.source_id}</span>
                  )}
                  {ev.relevance_score != null && (
                    <span className="ml-auto text-xs font-mono" style={{ color: ev.relevance_score > 0.7 ? "#22c55e" : "var(--text-muted)" }}>
                      {(ev.relevance_score * 100).toFixed(0)}% relevant
                    </span>
                  )}
                </div>
                <p className="text-xs font-mono leading-relaxed" style={{ color: "var(--text-secondary)", whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
                  {ev.content.slice(0, 400)}{ev.content.length > 400 ? "..." : ""}
                </p>
              </div>
            ))}
          </div>
        )}

        {/* Recommendations Tab */}
        {activeTab === "recommendations" && (
          <div className="space-y-4">
            <h2 className="text-sm font-semibold uppercase tracking-wider mb-4" style={{ color: "var(--text-muted)" }}>
              Remediation Recommendations
            </h2>
            {recommendations.length === 0 ? (
              <div className="glass-card p-6 text-center" style={{ color: "var(--text-muted)" }}>
                Recommendations will appear after investigation completes
              </div>
            ) : (
              recommendations.map(rec => (
                <div key={rec.id} className="glass-card p-6 animate-fade-in">
                  <div className="flex items-start justify-between mb-4">
                    <RiskBadge level={rec.risk_level} />
                    <span className="badge" style={{
                      background: rec.status === "APPROVED" ? "rgba(34,197,94,0.15)" : rec.status === "REJECTED" ? "rgba(239,68,68,0.15)" : "rgba(59,130,246,0.15)",
                      color: rec.status === "APPROVED" ? "#4ade80" : rec.status === "REJECTED" ? "#f87171" : "#60a5fa",
                      border: "1px solid",
                      borderColor: rec.status === "APPROVED" ? "rgba(34,197,94,0.3)" : rec.status === "REJECTED" ? "rgba(239,68,68,0.3)" : "rgba(59,130,246,0.3)",
                    }}>{rec.status}</span>
                  </div>

                  <h3 className="font-semibold mb-2" style={{ color: "var(--text-primary)" }}>{rec.action}</h3>
                  <p className="text-sm mb-4" style={{ color: "var(--text-secondary)" }}>{rec.reason}</p>

                  {rec.expected_outcome && (
                    <div className="text-xs mb-1" style={{ color: "var(--text-muted)" }}>
                      Expected: {rec.expected_outcome}
                    </div>
                  )}
                  {rec.rollback_strategy && (
                    <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                      Rollback: {rec.rollback_strategy}
                    </div>
                  )}

                  {rec.status === "PENDING" && rec.risk_level !== "LOW" && (
                    <div className="flex gap-3 mt-4 pt-4" style={{ borderTop: "1px solid var(--border)" }}>
                      <button
                        onClick={() => handleApprove(rec.id)}
                        disabled={approving === rec.id}
                        className="flex-1 py-2 rounded-lg text-sm font-semibold transition-all"
                        style={{ background: "rgba(34,197,94,0.2)", color: "#4ade80", border: "1px solid rgba(34,197,94,0.4)" }}
                      >
                        {approving === rec.id ? "Processing..." : "✓ Approve"}
                      </button>
                      <button
                        onClick={() => handleReject(rec.id)}
                        disabled={approving === rec.id}
                        className="flex-1 py-2 rounded-lg text-sm font-semibold transition-all"
                        style={{ background: "rgba(239,68,68,0.1)", color: "#f87171", border: "1px solid rgba(239,68,68,0.3)" }}
                      >
                        ✕ Reject
                      </button>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {/* Report Tab */}
        {activeTab === "report" && (
          <div className="max-w-3xl">
            <h2 className="text-sm font-semibold uppercase tracking-wider mb-4" style={{ color: "var(--text-muted)" }}>
              Final Investigation Report
            </h2>
            {incident?.final_report ? (
              <div className="glass-card p-6">
                <pre className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: "var(--text-secondary)", fontFamily: "Inter, sans-serif" }}>
                  {incident.final_report}
                </pre>
              </div>
            ) : (
              <div className="glass-card p-6 text-center" style={{ color: "var(--text-muted)" }}>
                Report will be generated when investigation is complete
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
