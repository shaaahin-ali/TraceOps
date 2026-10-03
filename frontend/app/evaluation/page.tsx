"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, BarChart2, CheckCircle, XCircle, AlertTriangle, Zap } from "lucide-react";
import { api } from "@/lib/api";

export default function EvaluationPage() {
  const router = useRouter();
  const [results, setResults] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getEvaluationResults()
      .then(setResults)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-primary)" }}>
      <div className="border-b" style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}>
        <div className="max-w-5xl mx-auto px-6 py-4">
          <div className="flex items-center gap-4 mb-3">
            <button onClick={() => router.push("/dashboard")}
              className="flex items-center gap-1.5 text-sm transition-colors"
              style={{ color: "var(--text-muted)" }}>
              <ArrowLeft className="w-4 h-4" /> Dashboard
            </button>
          </div>
          <div className="flex items-center gap-3">
            <BarChart2 className="w-5 h-5 text-blue-400" />
            <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
              Evaluation Benchmark
            </h1>
          </div>
          <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
            Agent accuracy measured against ground truth (held-out from agent)
          </p>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-6 py-8">
        {loading ? (
          <div className="glass-card p-8 text-center" style={{ color: "var(--text-muted)" }}>Loading results...</div>
        ) : !results || results.status === "no_results" ? (
          <div className="glass-card p-8 text-center">
            <AlertTriangle className="w-8 h-8 mx-auto mb-3" style={{ color: "var(--accent-yellow)" }} />
            <p className="font-medium mb-2" style={{ color: "var(--text-primary)" }}>No evaluation results yet</p>
            <p className="text-sm mb-4" style={{ color: "var(--text-secondary)" }}>
              Run the evaluation benchmark from the backend:
            </p>
            <code className="px-4 py-2 rounded text-sm font-mono block"
              style={{ background: "rgba(30,45,74,0.6)", color: "var(--accent-blue)", border: "1px solid var(--border)" }}>
              python scripts/run_evaluation.py
            </code>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Aggregate metrics */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {[
                { label: "Top-1 Accuracy", value: `${(results.top1_accuracy * 100).toFixed(1)}%`, target: "≥80%", good: results.top1_accuracy >= 0.8 },
                { label: "Top-3 Accuracy", value: `${(results.top3_accuracy * 100).toFixed(1)}%`, target: "≥95%", good: results.top3_accuracy >= 0.95 },
                { label: "Evidence Recall", value: `${(results.avg_evidence_recall * 100).toFixed(1)}%`, target: "≥85%", good: results.avg_evidence_recall >= 0.85 },
                { label: "Unsupported Claims", value: `${(results.unsupported_primary_claim_rate * 100).toFixed(1)}%`, target: "≤5%", good: results.unsupported_primary_claim_rate <= 0.05 },
              ].map(({ label, value, target, good }) => (
                <div key={label} className="glass-card p-5">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>{label}</span>
                    {good
                      ? <CheckCircle className="w-4 h-4" style={{ color: "var(--accent-green)" }} />
                      : <XCircle className="w-4 h-4" style={{ color: "var(--accent-red)" }} />
                    }
                  </div>
                  <div className="text-2xl font-bold mb-1" style={{ color: good ? "var(--accent-green)" : "var(--accent-red)" }}>{value}</div>
                  <div className="text-xs" style={{ color: "var(--text-muted)" }}>Target: {target}</div>
                </div>
              ))}
            </div>

            {/* Per-incident table */}
            <div className="glass-card overflow-hidden">
              <div className="px-6 py-4 border-b" style={{ borderColor: "var(--border)" }}>
                <h2 className="font-semibold" style={{ color: "var(--text-primary)" }}>Per-Incident Results</h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border)", color: "var(--text-muted)" }}>
                      <th className="text-left px-6 py-3 font-medium">Incident</th>
                      <th className="text-left px-4 py-3 font-medium">Top-1</th>
                      <th className="text-left px-4 py-3 font-medium">Top-3</th>
                      <th className="text-left px-4 py-3 font-medium">Confidence</th>
                      <th className="text-left px-4 py-3 font-medium">Duration</th>
                      <th className="text-left px-4 py-3 font-medium">Expected Root Cause</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(results.per_incident || []).filter((r: any) => !r.error).map((r: any) => (
                      <tr key={r.incident_id} style={{ borderBottom: "1px solid rgba(30,45,74,0.5)", color: "var(--text-secondary)" }}>
                        <td className="px-6 py-4 font-mono text-xs">{r.incident_id}</td>
                        <td className="px-4 py-4">
                          {r.top1_correct
                            ? <CheckCircle className="w-4 h-4" style={{ color: "var(--accent-green)" }} />
                            : <XCircle className="w-4 h-4" style={{ color: "var(--accent-red)" }} />}
                        </td>
                        <td className="px-4 py-4">
                          {r.top3_correct
                            ? <CheckCircle className="w-4 h-4" style={{ color: "var(--accent-green)" }} />
                            : <XCircle className="w-4 h-4" style={{ color: "var(--accent-red)" }} />}
                        </td>
                        <td className="px-4 py-4">
                          <span className="font-mono font-bold" style={{
                            color: r.confidence_score >= 80 ? "var(--accent-green)" : r.confidence_score >= 60 ? "var(--accent-blue)" : "var(--accent-yellow)"
                          }}>
                            {r.confidence_score?.toFixed(0)}/100
                          </span>
                        </td>
                        <td className="px-4 py-4 font-mono text-xs">{r.duration_seconds}s</td>
                        <td className="px-4 py-4 text-xs max-w-xs truncate">{r.expected_root_cause?.replace(/_/g, " ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="text-xs text-right" style={{ color: "var(--text-muted)" }}>
              Benchmark run: {results.benchmark_date ? new Date(results.benchmark_date).toLocaleString() : "—"}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
