"use client";

/**
 * Approvals Page — /approvals
 * ==============================
 * SRE/ADMIN-only queue of recommendations awaiting human review.
 *
 * Features:
 * - Shows all pending recommendations across all incidents
 * - One-click approve / reject with optional reason
 * - Risk-level colour coding (HIGH is red, MEDIUM is yellow, LOW is green)
 * - Role guard: non-SRE users see an access denied message
 * - Refreshes after each decision
 */

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Shield,
  ChevronDown,
  ChevronUp,
  ArrowLeft,
  RefreshCw,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { RiskBadge, StatusBadge } from "@/components/Badge";
import { Navbar } from "@/components/Navbar";
import type { Recommendation, Incident } from "@/types";

interface PendingItem {
  recommendation: Recommendation;
  incident: Incident | null;
}

// ── Approve/Reject Modal ───────────────────────────────────────

function ActionModal({
  rec,
  action,
  onConfirm,
  onCancel,
  loading,
}: {
  rec: Recommendation;
  action: "approve" | "reject";
  onConfirm: (reason: string) => void;
  onCancel: () => void;
  loading: boolean;
}) {
  const [reason, setReason] = useState("");
  const isApprove = action === "approve";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.7)" }}
    >
      <div
        className="glass-card p-6 w-full max-w-md animate-fade-in"
        style={{ border: `1px solid ${isApprove ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}` }}
      >
        <div className="flex items-center gap-3 mb-4">
          {isApprove ? (
            <CheckCircle2 className="w-5 h-5" style={{ color: "#4ade80" }} />
          ) : (
            <XCircle className="w-5 h-5" style={{ color: "#f87171" }} />
          )}
          <h2 className="font-bold text-lg" style={{ color: "var(--text-primary)" }}>
            {isApprove ? "Approve Recommendation" : "Reject Recommendation"}
          </h2>
        </div>

        <p className="text-sm mb-4" style={{ color: "var(--text-secondary)" }}>
          <strong style={{ color: "var(--text-primary)" }}>{rec.action}</strong>
        </p>

        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder={isApprove ? "Reason for approval (optional)" : "Reason for rejection (optional)"}
          className="w-full p-3 rounded-lg text-sm resize-none"
          rows={3}
          style={{
            background: "var(--bg-primary)",
            border: "1px solid var(--border)",
            color: "var(--text-primary)",
            outline: "none",
          }}
        />

        <div className="flex gap-3 mt-4">
          <button
            onClick={() => onConfirm(reason)}
            disabled={loading}
            className="flex-1 py-2 rounded-lg text-sm font-semibold transition-all"
            style={{
              background: isApprove ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.15)",
              color: isApprove ? "#4ade80" : "#f87171",
              border: `1px solid ${isApprove ? "rgba(34,197,94,0.4)" : "rgba(239,68,68,0.3)"}`,
              opacity: loading ? 0.6 : 1,
            }}
          >
            {loading ? "Processing..." : isApprove ? "✓ Confirm Approval" : "✕ Confirm Rejection"}
          </button>
          <button
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 rounded-lg text-sm transition-all"
            style={{ color: "var(--text-muted)", border: "1px solid var(--border)" }}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Recommendation Card ────────────────────────────────────────

function RecommendationCard({
  item,
  onApprove,
  onReject,
  loading,
}: {
  item: PendingItem;
  onApprove: () => void;
  onReject: () => void;
  loading: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const { recommendation: rec, incident } = item;

  return (
    <div className="glass-card p-6 animate-fade-in">
      {/* Header row */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3 flex-wrap">
          <RiskBadge level={rec.risk_level} />
          {incident && (
            <span
              className="text-xs font-mono px-2 py-0.5 rounded"
              style={{
                background: "rgba(59,130,246,0.1)",
                color: "var(--accent-blue)",
              }}
            >
              {incident.service}
            </span>
          )}
        </div>
        <button
          onClick={() => setExpanded((v) => !v)}
          className="text-xs flex items-center gap-1 transition-colors"
          style={{ color: "var(--text-muted)" }}
        >
          {expanded ? (
            <>
              Less <ChevronUp className="w-3.5 h-3.5" />
            </>
          ) : (
            <>
              Details <ChevronDown className="w-3.5 h-3.5" />
            </>
          )}
        </button>
      </div>

      {/* Incident context */}
      {incident && (
        <p className="text-xs mb-2" style={{ color: "var(--text-muted)" }}>
          Incident:{" "}
          <a
            href={`/investigation/${incident.id}`}
            className="hover:underline"
            style={{ color: "var(--accent-blue)" }}
          >
            {incident.title}
          </a>
        </p>
      )}

      {/* Action */}
      <h3 className="font-semibold mb-2" style={{ color: "var(--text-primary)" }}>
        {rec.action}
      </h3>
      <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
        {rec.reason}
      </p>

      {/* Expanded details */}
      {expanded && (
        <div className="mt-4 space-y-2 pt-4" style={{ borderTop: "1px solid var(--border)" }}>
          {rec.expected_outcome && (
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
                Expected Outcome
              </span>
              <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
                {rec.expected_outcome}
              </p>
            </div>
          )}
          {rec.potential_impact && (
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--accent-yellow)" }}>
                Potential Impact
              </span>
              <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
                {rec.potential_impact}
              </p>
            </div>
          )}
          {rec.rollback_strategy && (
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
                Rollback Strategy
              </span>
              <p className="text-sm font-mono mt-1" style={{ color: "var(--text-secondary)" }}>
                {rec.rollback_strategy}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-3 mt-5 pt-4" style={{ borderTop: "1px solid var(--border)" }}>
        <button
          onClick={onApprove}
          disabled={loading}
          id={`approve-${rec.id}`}
          className="flex-1 py-2.5 rounded-lg text-sm font-semibold transition-all flex items-center justify-center gap-2"
          style={{
            background: "rgba(34,197,94,0.15)",
            color: "#4ade80",
            border: "1px solid rgba(34,197,94,0.4)",
            opacity: loading ? 0.6 : 1,
          }}
        >
          <CheckCircle2 className="w-4 h-4" />
          {loading ? "Processing..." : "Approve"}
        </button>
        <button
          onClick={onReject}
          disabled={loading}
          id={`reject-${rec.id}`}
          className="flex-1 py-2.5 rounded-lg text-sm font-semibold transition-all flex items-center justify-center gap-2"
          style={{
            background: "rgba(239,68,68,0.1)",
            color: "#f87171",
            border: "1px solid rgba(239,68,68,0.3)",
            opacity: loading ? 0.6 : 1,
          }}
        >
          <XCircle className="w-4 h-4" />
          Reject
        </button>
      </div>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────

export default function ApprovalsPage() {
  const router = useRouter();
  const { user, isLoading, requireAuth, hasRole } = useAuth();

  const [items, setItems] = useState<PendingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [modal, setModal] = useState<{
    rec: Recommendation;
    action: "approve" | "reject";
  } | null>(null);
  const [acting, setActing] = useState(false);

  useEffect(() => {
    requireAuth();
  }, [requireAuth]);

  async function loadPending() {
    try {
      // Load all incidents, then collect pending recommendations
      const incidents: Incident[] = await api.getIncidents();
      const all: PendingItem[] = [];

      await Promise.all(
        incidents.map(async (incident) => {
          const recs: Recommendation[] = await api.getRecommendations(incident.id);
          for (const rec of recs) {
            if (rec.status === "PENDING" && rec.risk_level !== "LOW") {
              all.push({ recommendation: rec, incident });
            }
          }
        })
      );

      // Sort: HIGH risk first, then MEDIUM
      all.sort((a, b) => {
        const order = { HIGH: 0, MEDIUM: 1, LOW: 2 };
        return (
          (order[a.recommendation.risk_level as keyof typeof order] ?? 2) -
          (order[b.recommendation.risk_level as keyof typeof order] ?? 2)
        );
      });

      setItems(all);
    } catch (e: any) {
      console.error("Failed to load pending approvals:", e.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    if (!isLoading) loadPending();
  }, [isLoading]);

  function refresh() {
    setRefreshing(true);
    loadPending();
  }

  async function handleDecision(reason: string) {
    if (!modal) return;
    setActing(true);
    try {
      if (modal.action === "approve") {
        await api.approve(modal.rec.id, reason);
      } else {
        await api.reject(modal.rec.id, reason);
      }
      setModal(null);
      await loadPending();
    } finally {
      setActing(false);
    }
  }

  if (isLoading || loading) {
    return (
      <div
        className="flex items-center justify-center min-h-screen"
        style={{ background: "var(--bg-primary)" }}
      >
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <span style={{ color: "var(--text-secondary)" }}>Loading approvals...</span>
        </div>
      </div>
    );
  }

  // Role guard — non-SRE/ADMIN users see access denied
  if (!hasRole("SRE", "ADMIN")) {
    return (
      <div style={{ background: "var(--bg-primary)", minHeight: "100vh" }}>
        <Navbar />
        <div className="max-w-2xl mx-auto px-6 py-20 text-center">
          <AlertTriangle className="w-12 h-12 mx-auto mb-4" style={{ color: "var(--accent-yellow)" }} />
          <h1 className="text-2xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>
            Access Denied
          </h1>
          <p style={{ color: "var(--text-secondary)" }}>
            This page is restricted to <strong>SRE</strong> and <strong>ADMIN</strong> roles.
            Contact your administrator to request access.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ background: "var(--bg-primary)", minHeight: "100vh" }}>
      <Navbar />

      {/* Header */}
      <div
        className="border-b"
        style={{ borderColor: "var(--border)", background: "var(--bg-secondary)" }}
      >
        <div className="max-w-5xl mx-auto px-6 py-6">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-3 mb-1">
                <Shield className="w-5 h-5 text-blue-400" />
                <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
                  Pending Approvals
                </h1>
                {items.length > 0 && (
                  <span
                    className="px-2 py-0.5 rounded-full text-xs font-bold"
                    style={{
                      background: "rgba(239,68,68,0.15)",
                      color: "#f87171",
                      border: "1px solid rgba(239,68,68,0.3)",
                    }}
                  >
                    {items.length} pending
                  </span>
                )}
              </div>
              <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                HIGH and MEDIUM risk recommendations require your review before execution
              </p>
            </div>
            <button
              onClick={refresh}
              disabled={refreshing}
              className="flex items-center gap-1.5 text-sm px-3 py-2 rounded-lg transition-all"
              style={{
                color: "var(--text-muted)",
                border: "1px solid var(--border)",
                opacity: refreshing ? 0.6 : 1,
              }}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-5xl mx-auto px-6 py-8">
        {items.length === 0 ? (
          <div className="glass-card p-12 text-center">
            <CheckCircle2
              className="w-12 h-12 mx-auto mb-4"
              style={{ color: "var(--accent-green)" }}
            />
            <h2 className="text-lg font-semibold mb-2" style={{ color: "var(--text-primary)" }}>
              No pending approvals
            </h2>
            <p style={{ color: "var(--text-muted)" }}>
              All recommendations have been reviewed. Check back after new investigations complete.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {items.map((item) => (
              <RecommendationCard
                key={item.recommendation.id}
                item={item}
                loading={acting}
                onApprove={() =>
                  setModal({ rec: item.recommendation, action: "approve" })
                }
                onReject={() =>
                  setModal({ rec: item.recommendation, action: "reject" })
                }
              />
            ))}
          </div>
        )}
      </div>

      {/* Modal */}
      {modal && (
        <ActionModal
          rec={modal.rec}
          action={modal.action}
          loading={acting}
          onConfirm={handleDecision}
          onCancel={() => setModal(null)}
        />
      )}
    </div>
  );
}
