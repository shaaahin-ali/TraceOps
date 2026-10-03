"""Initial schema — all tables

Revision ID: 001_initial
Revises:
Create Date: 2026-09-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ── users ─────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, default="USER"),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── incidents ─────────────────────────────────────────────
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("service", sa.String(255), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False, default="MEDIUM"),
        sa.Column("status", sa.String(32), nullable=False, default="OPEN"),
        sa.Column("incident_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(64), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("final_report", sa.Text(), nullable=True),
        sa.Column("analyzed_symptoms", postgresql.JSONB(), nullable=True),
        sa.Column("analyzed_time_range", postgresql.JSONB(), nullable=True),
        sa.Column("investigation_plan", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── documents ─────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("document_type", sa.String(64), nullable=False),
        sa.Column("service", sa.String(255), nullable=True),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── document_chunks ───────────────────────────────────────
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("document_id", sa.String(64), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column("chunk_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Add pgvector column separately using raw SQL (alembic doesn't know the vector type)
    op.execute("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding vector(768)")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(768)")

    # ── deployments ───────────────────────────────────────────
    op.create_table(
        "deployments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("service", sa.String(255), nullable=False),
        sa.Column("version", sa.String(128), nullable=False),
        sa.Column("commit_sha", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, default="SUCCESS"),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deployed_by", sa.String(128), nullable=True),
        sa.Column("deployment_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── logs ──────────────────────────────────────────────────
    op.create_table(
        "logs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("service", sa.String(255), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("request_id", sa.String(128), nullable=True),
        sa.Column("log_metadata", postgresql.JSONB(), nullable=True),
    )

    # ── metrics ───────────────────────────────────────────────
    op.create_table(
        "metrics",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("service", sa.String(255), nullable=False),
        sa.Column("metric_name", sa.String(128), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("metric_metadata", postgresql.JSONB(), nullable=True),
    )

    # ── hypotheses ────────────────────────────────────────────
    op.create_table(
        "hypotheses",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("incident_id", sa.String(64), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("hypothesis_id", sa.String(16), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("missing_evidence", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── evidence ──────────────────────────────────────────────
    op.create_table(
        "evidence",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("incident_id", sa.String(64), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(256), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("supports", postgresql.JSONB(), nullable=True),
        sa.Column("contradicts", postgresql.JSONB(), nullable=True),
        sa.Column("evidence_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── recommendations ───────────────────────────────────────
    op.create_table(
        "recommendations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("incident_id", sa.String(64), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("risk_level", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, default="PENDING"),
        sa.Column("expected_outcome", sa.Text(), nullable=True),
        sa.Column("potential_impact", sa.Text(), nullable=True),
        sa.Column("rollback_strategy", sa.Text(), nullable=True),
        sa.Column("supporting_evidence", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── investigation_events ──────────────────────────────────
    op.create_table(
        "investigation_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("incident_id", sa.String(64), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("agent_node", sa.String(128), nullable=True),
        sa.Column("tool_name", sa.String(128), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, default=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── approvals ─────────────────────────────────────────────
    op.create_table(
        "approvals",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("recommendation_id", sa.String(64), sa.ForeignKey("recommendations.id"), nullable=False),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Indexes ────────────────────────────────────────────────
    op.create_index("idx_logs_service_timestamp", "logs", ["service", "timestamp"])
    op.create_index("idx_metrics_service_metric_timestamp", "metrics", ["service", "metric_name", "timestamp"])
    op.create_index("idx_deployments_service_deployed_at", "deployments", ["service", "deployed_at"])
    op.create_index("idx_incidents_status", "incidents", ["status"])
    op.create_index("idx_hypotheses_incident", "hypotheses", ["incident_id"])
    op.create_index("idx_evidence_incident", "evidence", ["incident_id"])


def downgrade() -> None:
    op.drop_table("approvals")
    op.drop_table("investigation_events")
    op.drop_table("recommendations")
    op.drop_table("evidence")
    op.drop_table("hypotheses")
    op.drop_table("metrics")
    op.drop_table("logs")
    op.drop_table("deployments")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("incidents")
    op.drop_table("users")
