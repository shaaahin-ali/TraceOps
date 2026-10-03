/**
 * RootTrace TypeScript Types
 * ============================
 * Shared type definitions for all frontend components and API responses.
 * Matches the Pydantic schemas in the backend.
 */

// ── Enums ─────────────────────────────────────────────────────

export type UserRole = "USER" | "SRE" | "ADMIN";

export type IncidentSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type IncidentStatus = "OPEN" | "INVESTIGATING" | "RESOLVED" | "CLOSED";

export type HypothesisStatus =
  | "PENDING"
  | "TESTING"
  | "SUPPORTED"
  | "PARTIALLY_SUPPORTED"
  | "UNSUPPORTED"
  | "CONTRADICTED";

export type EvidenceSourceType =
  | "LOG"
  | "METRIC"
  | "DEPLOYMENT"
  | "GIT_COMMIT"
  | "GIT_DIFF"
  | "KNOWLEDGE_BASE"
  | "HISTORICAL_INCIDENT";

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";

export type RecommendationStatus =
  | "PENDING"
  | "APPROVED"
  | "REJECTED"
  | "SIMULATED";

export type InvestigationEventType =
  | "INCIDENT_RECEIVED"
  | "INCIDENT_CLASSIFIED"
  | "PLAN_CREATED"
  | "TOOL_CALLED"
  | "TOOL_RESULT"
  | "EVIDENCE_FOUND"
  | "HYPOTHESES_GENERATED"
  | "HYPOTHESIS_TESTED"
  | "VALIDATION_COMPLETED"
  | "ROOT_CAUSE_RANKED"
  | "RECOMMENDATION_GENERATED"
  | "HUMAN_APPROVAL_REQUIRED"
  | "HUMAN_APPROVED"
  | "HUMAN_REJECTED"
  | "REPORT_GENERATED"
  | "INVESTIGATION_FAILED"
  | "INVESTIGATION_COMPLETED";

// ── Core Entities ─────────────────────────────────────────────

export interface User {
  user_id: string;
  name: string;
  email: string;
  role: UserRole;
}

export interface Incident {
  id: string;
  title: string;
  description: string;
  service: string;
  severity: IncidentSeverity;
  status: IncidentStatus;
  incident_time: string | null;
  created_at: string;
  confidence_score: number | null;
}

export interface Hypothesis {
  id: string;
  hypothesis_id: string; // "H1", "H2", etc.
  description: string;
  status: HypothesisStatus;
  confidence_score: number | null;
  rank: number | null;
  missing_evidence: string[] | null;
}

export interface Evidence {
  id: string;
  source_type: EvidenceSourceType;
  source_id: string | null;
  content: string;
  relevance_score: number | null;
  supports: string[] | null;
  contradicts: string[] | null;
  timestamp: string | null;
}

export interface Recommendation {
  id: string;
  action: string;
  reason: string;
  risk_level: RiskLevel;
  status: RecommendationStatus;
  expected_outcome: string | null;
  potential_impact: string | null;
  rollback_strategy: string | null;
}

export interface InvestigationEvent {
  id: string;
  event_type: InvestigationEventType;
  agent_node: string | null;
  tool_name: string | null;
  summary: string | null;
  success: boolean;
  timestamp: string;
}

// ── Evaluation ────────────────────────────────────────────────

export interface PerIncidentResult {
  incident_id: string;
  ground_truth_id: string;
  top1_correct: boolean;
  top3_correct: boolean;
  confidence_score: number;
  duration_seconds: number;
  expected_root_cause: string;
  error?: string;
}

export interface EvaluationResults {
  benchmark_date: string;
  incidents_tested: number;
  top1_accuracy: number;
  top3_accuracy: number;
  avg_evidence_recall: number;
  avg_confidence: number;
  avg_tool_calls: number;
  avg_hypotheses: number;
  avg_duration_seconds: number;
  unsupported_primary_claim_rate: number;
  human_escalation_rate: number;
  per_incident: PerIncidentResult[];
  status?: "no_results";
  message?: string;
}

// ── API Request / Response ────────────────────────────────────

export interface CreateIncidentPayload {
  title: string;
  description: string;
  service: string;
  severity: IncidentSeverity;
  incident_time?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  name: string;
  email: string;
  role: UserRole;
}

export interface ApprovalResponse {
  status: "APPROVED" | "REJECTED";
  recommendation_id: string;
  approved_by?: string;
  rejected_by?: string;
  note?: string;
}

// ── UI State ──────────────────────────────────────────────────

export interface InvestigationData {
  incident: Incident | null;
  events: InvestigationEvent[];
  hypotheses: Hypothesis[];
  evidence: Evidence[];
  recommendations: Recommendation[];
}
