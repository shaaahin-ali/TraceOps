"use client";

/**
 * Badge Components
 * =================
 * Shared badge/pill components used across investigation pages.
 * Extracted from investigation page to eliminate duplication.
 */

import type {
  IncidentSeverity,
  IncidentStatus,
  HypothesisStatus,
  RiskLevel,
  RecommendationStatus,
} from "@/types";

// ── Status Badge ──────────────────────────────────────────────

interface StatusBadgeProps {
  status: IncidentStatus | string;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const s = status.toLowerCase();
  const cls =
    s.includes("investigat")
      ? "badge-investigating"
      : status === "RESOLVED"
      ? "badge-resolved"
      : status === "OPEN"
      ? "badge-open"
      : "badge-investigating";
  return <span className={`badge ${cls}`}>{status}</span>;
}

// ── Severity Badge ────────────────────────────────────────────

interface SeverityBadgeProps {
  severity: IncidentSeverity | string;
}

export function SeverityBadge({ severity }: SeverityBadgeProps) {
  const cls =
    severity === "CRITICAL"
      ? "badge-critical"
      : severity === "HIGH"
      ? "badge-high"
      : severity === "MEDIUM"
      ? "badge-medium"
      : "badge-low";
  return <span className={`badge ${cls}`}>{severity}</span>;
}

// ── Hypothesis Badge ──────────────────────────────────────────

interface HypothesisBadgeProps {
  status: HypothesisStatus | string;
}

export function HypothesisBadge({ status }: HypothesisBadgeProps) {
  if (!status) return null;
  const cls =
    status === "SUPPORTED"
      ? "badge-supported"
      : status === "PARTIALLY_SUPPORTED"
      ? "badge-partial"
      : "badge-unsupported";
  return (
    <span className={`badge ${cls}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

// ── Risk Badge ────────────────────────────────────────────────

interface RiskBadgeProps {
  level: RiskLevel | string;
}

export function RiskBadge({ level }: RiskBadgeProps) {
  const cls =
    level === "HIGH"
      ? "badge-critical"
      : level === "MEDIUM"
      ? "badge-medium"
      : "badge-low";
  return <span className={`badge ${cls}`}>{level} RISK</span>;
}

// ── Recommendation Status Badge ───────────────────────────────

interface RecStatusBadgeProps {
  status: RecommendationStatus | string;
}

export function RecStatusBadge({ status }: RecStatusBadgeProps) {
  const styles: Record<string, { bg: string; color: string; border: string }> =
    {
      APPROVED: {
        bg: "rgba(34,197,94,0.15)",
        color: "#4ade80",
        border: "rgba(34,197,94,0.3)",
      },
      REJECTED: {
        bg: "rgba(239,68,68,0.15)",
        color: "#f87171",
        border: "rgba(239,68,68,0.3)",
      },
      PENDING: {
        bg: "rgba(59,130,246,0.15)",
        color: "#60a5fa",
        border: "rgba(59,130,246,0.3)",
      },
      SIMULATED: {
        bg: "rgba(168,85,247,0.15)",
        color: "#c084fc",
        border: "rgba(168,85,247,0.3)",
      },
    };
  const s = styles[status] ?? styles.PENDING;
  return (
    <span
      className="badge"
      style={{
        background: s.bg,
        color: s.color,
        border: `1px solid ${s.border}`,
      }}
    >
      {status}
    </span>
  );
}
