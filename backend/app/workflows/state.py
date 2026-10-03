"""
RootTrace Investigation State
================================
The complete typed state passed between all LangGraph agent nodes.

🎓 WHY TYPED STATE MATTERS:
LangGraph passes state between nodes. Using Pydantic models means:
1. Type errors are caught at runtime, not hidden in dict access bugs
2. The IDE can autocomplete every field
3. The state is self-documenting
4. We can validate state transitions
5. The state can be serialized to JSON for storage

🎓 IMMUTABILITY PATTERN:
Each node receives the current state and returns UPDATES (not the whole state).
LangGraph merges the updates into the state.
This prevents nodes from accidentally overwriting each other's work.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from enum import Enum

from pydantic import BaseModel, Field
import operator


# ── Enumerations ────────────────────────────────────────────


class InvestigationStatus(str, Enum):
    PENDING = "PENDING"
    ANALYZING = "ANALYZING"
    PLANNING = "PLANNING"
    COLLECTING = "COLLECTING"
    HYPOTHESIZING = "HYPOTHESIZING"
    TESTING = "TESTING"
    VALIDATING = "VALIDATING"
    RANKING = "RANKING"
    REMEDIATING = "REMEDIATING"
    SAFETY_CHECK = "SAFETY_CHECK"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    REPORTING = "REPORTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class HypothesisValidationResult(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# ── Sub-models ───────────────────────────────────────────────


class IncidentAnalysis(BaseModel):
    """Structured output from the IncidentAnalyzer node."""
    service: str
    symptoms: list[str]
    time_range: dict[str, str]  # {"start": "...", "end": "..."}
    severity: str
    affected_components: list[str]
    investigation_priority: str


class InvestigationPlan(BaseModel):
    """Structured output from the Planner node."""
    required_data_sources: list[str]
    investigation_steps: list[str]
    priority_hypotheses: list[str]
    time_range_to_investigate: dict[str, str]
    rationale: str


class EvidenceItem(BaseModel):
    """A single piece of collected evidence."""
    id: str
    source_type: str         # log, metric, deployment, git_commit, etc.
    source_id: str | None    # commit SHA, log ID, deployment ID
    content: str             # what the evidence actually says
    timestamp: str | None
    relevance: float = 0.0
    supports: list[str] = Field(default_factory=list)   # hypothesis IDs
    contradicts: list[str] = Field(default_factory=list)


class Hypothesis(BaseModel):
    """A root-cause hypothesis."""
    id: str                    # H1, H2, H3...
    description: str
    supporting_evidence: list[str] = Field(default_factory=list)   # evidence IDs
    contradicting_evidence: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    validation_status: HypothesisValidationResult | None = None
    confidence_score: float = 0.0
    rank: int | None = None
    reasoning: str = ""


class Recommendation(BaseModel):
    """A remediation recommendation."""
    id: str
    action: str
    reason: str
    risk_level: RiskLevel
    expected_outcome: str
    potential_impact: str
    rollback_strategy: str
    supporting_evidence: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    approval_status: str | None = None


class Contradiction(BaseModel):
    """A detected contradiction between evidence items or hypotheses."""
    description: str
    evidence_ids: list[str]
    affected_hypotheses: list[str]


# ── Main Investigation State ─────────────────────────────────


class InvestigationState(BaseModel):
    """
    Complete state of an investigation.
    Passed between all LangGraph nodes.

    🎓 The Annotated[list, operator.add] pattern tells LangGraph
    to APPEND to these lists (not replace them) when nodes return updates.
    This allows multiple nodes to add evidence without conflicts.
    """

    # ── Incident Input ───────────────────────────────────────
    incident_id: str
    incident_title: str
    incident_description: str
    incident_service: str
    incident_time: str

    # ── Status ───────────────────────────────────────────────
    status: InvestigationStatus = InvestigationStatus.PENDING
    started_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: str | None = None

    # ── Analysis ─────────────────────────────────────────────
    incident_analysis: IncidentAnalysis | None = None
    investigation_plan: InvestigationPlan | None = None

    # ── Evidence (append-only via operator.add) ──────────────
    collected_evidence: list[EvidenceItem] = Field(default_factory=list)
    retrieved_documents: list[dict] = Field(default_factory=list)

    # ── Tool Usage Tracking ──────────────────────────────────
    tools_called: list[str] = Field(default_factory=list)
    tool_call_count: int = 0
    max_tool_calls: int = 20

    # ── Hypotheses ───────────────────────────────────────────
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)

    # ── Root Cause ───────────────────────────────────────────
    ranked_root_causes: list[Hypothesis] = Field(default_factory=list)
    primary_root_cause: Hypothesis | None = None
    overall_confidence: float = 0.0

    # ── Remediation ──────────────────────────────────────────
    recommendations: list[Recommendation] = Field(default_factory=list)
    requires_human_approval: bool = False
    approval_status: str | None = None  # APPROVED, REJECTED, PENDING

    # ── Report ───────────────────────────────────────────────
    final_report: str | None = None

    # ── Error Tracking ───────────────────────────────────────
    errors: list[str] = Field(default_factory=list)
    unavailable_sources: list[str] = Field(default_factory=list)

    class Config:
        use_enum_values = True

    def can_call_tool(self) -> bool:
        """Check if we've hit the tool call limit."""
        return self.tool_call_count < self.max_tool_calls

    def add_evidence(self, item: EvidenceItem) -> None:
        """Add evidence and track source type."""
        self.collected_evidence.append(item)

    def evidence_by_id(self, evidence_id: str) -> EvidenceItem | None:
        return next((e for e in self.collected_evidence if e.id == evidence_id), None)

    def hypothesis_by_id(self, h_id: str) -> Hypothesis | None:
        return next((h for h in self.hypotheses if h.id == h_id), None)

    def supporting_evidence_for(self, hypothesis_id: str) -> list[EvidenceItem]:
        return [e for e in self.collected_evidence if hypothesis_id in e.supports]

    def contradicting_evidence_for(self, hypothesis_id: str) -> list[EvidenceItem]:
        return [e for e in self.collected_evidence if hypothesis_id in e.contradicts]
