"""
RootTrace Database Models — Phase 2
=====================================
All SQLAlchemy ORM models with full relationships.

🎓 Learning Moment — SQLAlchemy 2.0 Mapped Columns:
- `Mapped[str]` = NOT NULL column
- `Mapped[str | None]` = NULLABLE column
- `mapped_column()` adds column-level constraints
- Relationships defined on both sides for bidirectional access

🎓 Why separate models from schemas?
- Models = database structure (SQLAlchemy)
- Schemas = API structure (Pydantic)
- Keeping them separate lets the DB and API evolve independently
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.config import get_settings

settings = get_settings()


# ── Enumerations ─────────────────────────────────────────────


class UserRole(str, PyEnum):
    USER = "USER"
    SRE = "SRE"
    ADMIN = "ADMIN"


class IncidentSeverity(str, PyEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, PyEnum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class HypothesisStatus(str, PyEnum):
    PENDING = "PENDING"
    TESTING = "TESTING"
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"


class EvidenceSourceType(str, PyEnum):
    LOG = "LOG"
    METRIC = "METRIC"
    DEPLOYMENT = "DEPLOYMENT"
    GIT_COMMIT = "GIT_COMMIT"
    GIT_DIFF = "GIT_DIFF"
    KNOWLEDGE_BASE = "KNOWLEDGE_BASE"
    HISTORICAL_INCIDENT = "HISTORICAL_INCIDENT"


class RiskLevel(str, PyEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RecommendationStatus(str, PyEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SIMULATED = "SIMULATED"


class InvestigationEventType(str, PyEnum):
    INCIDENT_RECEIVED = "INCIDENT_RECEIVED"
    INCIDENT_CLASSIFIED = "INCIDENT_CLASSIFIED"
    PLAN_CREATED = "PLAN_CREATED"
    TOOL_CALLED = "TOOL_CALLED"
    TOOL_RESULT = "TOOL_RESULT"
    EVIDENCE_FOUND = "EVIDENCE_FOUND"
    HYPOTHESES_GENERATED = "HYPOTHESES_GENERATED"
    HYPOTHESIS_TESTED = "HYPOTHESIS_TESTED"
    VALIDATION_COMPLETED = "VALIDATION_COMPLETED"
    ROOT_CAUSE_RANKED = "ROOT_CAUSE_RANKED"
    RECOMMENDATION_GENERATED = "RECOMMENDATION_GENERATED"
    HUMAN_APPROVAL_REQUIRED = "HUMAN_APPROVAL_REQUIRED"
    HUMAN_APPROVED = "HUMAN_APPROVED"
    HUMAN_REJECTED = "HUMAN_REJECTED"
    REPORT_GENERATED = "REPORT_GENERATED"
    INVESTIGATION_FAILED = "INVESTIGATION_FAILED"
    INVESTIGATION_COMPLETED = "INVESTIGATION_COMPLETED"


class DocumentType(str, PyEnum):
    ARCHITECTURE = "architecture"
    API_DOCS = "api_docs"
    RUNBOOK = "runbook"
    TROUBLESHOOTING = "troubleshooting"
    POSTMORTEM = "postmortem"
    HISTORICAL_INCIDENT = "historical_incident"


# ── Models ────────────────────────────────────────────────────


class User(Base):
    """
    System users with role-based access control.
    Passwords are NEVER stored in plaintext — only bcrypt hashes.
    """
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.USER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    approvals: Mapped[list["Approval"]] = relationship("Approval", back_populates="user")


class Incident(Base):
    """
    A software incident submitted by a user for investigation.
    This is the root entity — everything else hangs off an incident.
    """
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    service: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    severity: Mapped[IncidentSeverity] = mapped_column(Enum(IncidentSeverity), default=IncidentSeverity.MEDIUM)
    status: Mapped[IncidentStatus] = mapped_column(Enum(IncidentStatus), default=IncidentStatus.OPEN, index=True)
    incident_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str | None] = mapped_column(String, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Structured analysis from IncidentAnalyzer agent node
    analyzed_symptoms: Mapped[list | None] = mapped_column(JSON)
    analyzed_time_range: Mapped[dict | None] = mapped_column(JSON)
    investigation_plan: Mapped[dict | None] = mapped_column(JSON)
    final_report: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[float | None] = mapped_column(Float)

    # Relationships
    hypotheses: Mapped[list["Hypothesis"]] = relationship("Hypothesis", back_populates="incident", cascade="all, delete-orphan")
    evidence_items: Mapped[list["Evidence"]] = relationship("Evidence", back_populates="incident", cascade="all, delete-orphan")
    recommendations: Mapped[list["Recommendation"]] = relationship("Recommendation", back_populates="incident", cascade="all, delete-orphan")
    events: Mapped[list["InvestigationEvent"]] = relationship("InvestigationEvent", back_populates="incident", cascade="all, delete-orphan")


class Document(Base):
    """
    Engineering knowledge base documents (runbooks, postmortems, etc.)
    The document itself; chunks are stored in DocumentChunk.
    """
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    document_type: Mapped[DocumentType] = mapped_column(Enum(DocumentType))
    service: Mapped[str | None] = mapped_column(String(255), index=True)
    version: Mapped[str | None] = mapped_column(String(50))
    file_path: Mapped[str | None] = mapped_column(String(1000))
    content_hash: Mapped[str | None] = mapped_column(String(64))   # SHA-256 for dedup
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    chunks: Mapped[list["DocumentChunk"]] = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """
    A chunk of a document with its embedding vector.

    🎓 Key concept — pgvector:
    The `embedding` column stores a dense float vector.
    pgvector adds an HNSW or IVFFlat index for fast approximate nearest-neighbor search.
    Similarity search: SELECT ... ORDER BY embedding <=> query_vector LIMIT 5;
    """
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(String, ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Vector column — dimension must match embedding model output
    embedding: Mapped[list[float] | None] = mapped_column(Vector(settings.embedding_dimension))
    # Metadata for filtering (service, doc_type, section, etc.)
    chunk_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")


class Deployment(Base):
    """
    Simulated deployment records for the incident lab.
    The agent searches this to find deployments near the incident time.
    """
    __tablename__ = "deployments"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "DEP-001"
    service: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="SUCCESS")
    deployed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    deployed_by: Mapped[str | None] = mapped_column(String(255))
    deployment_metadata: Mapped[dict] = mapped_column(JSON, default=dict)


class LogEntry(Base):
    """
    Simulated application log entries.
    Indexed on service + timestamp + level for efficient querying.
    """
    __tablename__ = "logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    service: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # INFO, WARN, ERROR
    message: Mapped[str] = mapped_column(Text, nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(100))
    trace_id: Mapped[str | None] = mapped_column(String(100))
    log_metadata: Mapped[dict] = mapped_column(JSON, default=dict)


class Metric(Base):
    """
    Simulated time-series metric data.
    Indexed on service + metric_name + timestamp for range queries.
    """
    __tablename__ = "metrics"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    service: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    metric_metadata: Mapped[dict] = mapped_column(JSON, default=dict)


class Hypothesis(Base):
    """
    A root-cause hypothesis generated by the agent.
    Each hypothesis tracks its own supporting/contradicting evidence.
    """
    __tablename__ = "hypotheses"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_id: Mapped[str] = mapped_column(String, ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    hypothesis_id: Mapped[str] = mapped_column(String(10))  # H1, H2, H3
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[HypothesisStatus] = mapped_column(Enum(HypothesisStatus), default=HypothesisStatus.PENDING)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    rank: Mapped[int | None] = mapped_column(Integer)
    missing_evidence: Mapped[list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    incident: Mapped["Incident"] = relationship("Incident", back_populates="hypotheses")
    evidence_items: Mapped[list["Evidence"]] = relationship("Evidence", back_populates="hypothesis")


class Evidence(Base):
    """
    A piece of evidence collected during investigation.
    Links to an incident and optionally to a specific hypothesis.

    🎓 Key design — supports/contradicts arrays:
    One piece of evidence can support multiple hypotheses or contradict others.
    This allows the agent to build a proper evidence graph.
    """
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_id: Mapped[str] = mapped_column(String, ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    hypothesis_id: Mapped[str | None] = mapped_column(String, ForeignKey("hypotheses.id", ondelete="SET NULL"))
    source_type: Mapped[EvidenceSourceType] = mapped_column(Enum(EvidenceSourceType))
    source_id: Mapped[str | None] = mapped_column(String(255))  # e.g. commit SHA, log ID
    content: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    relevance_score: Mapped[float | None] = mapped_column(Float)
    supports: Mapped[list | None] = mapped_column(JSON)      # list of hypothesis IDs
    contradicts: Mapped[list | None] = mapped_column(JSON)   # list of hypothesis IDs
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    incident: Mapped["Incident"] = relationship("Incident", back_populates="evidence_items")
    hypothesis: Mapped["Hypothesis | None"] = relationship("Hypothesis", back_populates="evidence_items")


class Recommendation(Base):
    """
    A remediation recommendation generated by the agent.
    HIGH/MEDIUM risk recommendations require human approval.
    """
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_id: Mapped[str] = mapped_column(String, ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), nullable=False)
    status: Mapped[RecommendationStatus] = mapped_column(Enum(RecommendationStatus), default=RecommendationStatus.PENDING)
    expected_outcome: Mapped[str | None] = mapped_column(Text)
    potential_impact: Mapped[str | None] = mapped_column(Text)
    rollback_strategy: Mapped[str | None] = mapped_column(Text)
    supporting_evidence: Mapped[list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    incident: Mapped["Incident"] = relationship("Incident", back_populates="recommendations")
    approvals: Mapped[list["Approval"]] = relationship("Approval", back_populates="recommendation")


class InvestigationEvent(Base):
    """
    Complete audit trail of every agent action.
    Every tool call, every evidence finding, every state transition
    is recorded here. This IS the investigation trace.
    """
    __tablename__ = "investigation_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_id: Mapped[str] = mapped_column(String, ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    agent_node: Mapped[str | None] = mapped_column(String(100))   # which LangGraph node
    event_type: Mapped[InvestigationEventType] = mapped_column(Enum(InvestigationEventType))
    tool_name: Mapped[str | None] = mapped_column(String(100))
    tool_input: Mapped[dict | None] = mapped_column(JSON)
    tool_output: Mapped[dict | None] = mapped_column(JSON)
    summary: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    incident: Mapped["Incident"] = relationship("Incident", back_populates="events")


class Approval(Base):
    """
    Human approval/rejection record for risky recommendations.
    The decision is permanent and cannot be overwritten.
    In MVP: no real action is taken, only the decision is recorded.
    """
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    recommendation_id: Mapped[str] = mapped_column(String, ForeignKey("recommendations.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(10))   # "APPROVED" or "REJECTED"
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    recommendation: Mapped["Recommendation"] = relationship("Recommendation", back_populates="approvals")
    user: Mapped["User"] = relationship("User", back_populates="approvals")
