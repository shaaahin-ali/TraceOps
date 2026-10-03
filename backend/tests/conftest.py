"""
Shared Test Fixtures
======================
pytest conftest.py — automatically loaded by pytest for all tests
in this directory and below.

Design decisions:
- Uses pytest-asyncio for async tests
- All DB tests use a fresh in-memory SQLite database (no PostgreSQL needed)
- Mock objects are constructed as minimal Pydantic instances
- Heavy external dependencies (LLM, embeddings) are always mocked

Setup:
    pip install pytest pytest-asyncio httpx
"""

import asyncio
from typing import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
import pytest_asyncio

from app.workflows.state import (
    InvestigationState,
    InvestigationStatus,
    IncidentAnalysis,
    InvestigationPlan,
    EvidenceItem,
    Hypothesis,
    HypothesisValidationResult,
    Recommendation,
    RiskLevel,
)


# ── pytest-asyncio configuration ─────────────────────────────

@pytest.fixture(scope="session")
def event_loop_policy():
    """Use the default event loop policy."""
    return asyncio.DefaultEventLoopPolicy()


# ── State Factories ───────────────────────────────────────────


@pytest.fixture
def incident_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def base_state(incident_id: str) -> InvestigationState:
    """
    A minimal valid InvestigationState for testing node functions.
    Represents a newly received incident before any processing.
    """
    return InvestigationState(
        incident_id=incident_id,
        incident_title="Payment API latency increased 300% after latest deployment",
        incident_description=(
            "Users are experiencing significant payment processing delays. "
            "API response times have gone from ~120ms to over 600ms."
        ),
        incident_service="payment-api",
        incident_time="2026-09-06T10:30:00Z",
    )


@pytest.fixture
def analyzed_state(base_state: InvestigationState) -> InvestigationState:
    """State after analyze_incident node has run."""
    state = base_state.model_copy(deep=True)
    state.incident_analysis = IncidentAnalysis(
        service="payment-api",
        symptoms=["high API latency", "request timeouts"],
        time_range={
            "start": "2026-09-06T08:30:00Z",
            "end": "2026-09-06T11:30:00Z",
        },
        severity="HIGH",
        affected_components=["payment-api", "database"],
        investigation_priority="HIGH",
    )
    state.status = InvestigationStatus.PLANNING
    return state


@pytest.fixture
def state_with_evidence(analyzed_state: InvestigationState) -> InvestigationState:
    """State with collected evidence items."""
    state = analyzed_state.model_copy(deep=True)
    state.collected_evidence = [
        EvidenceItem(
            id="ev-001",
            source_type="deployment",
            source_id="DEP-001",
            content="Deployment DEP-001: commit abc123, deployed at 10:20Z",
            timestamp="2026-09-06T10:20:00Z",
            relevance=0.95,
        ),
        EvidenceItem(
            id="ev-002",
            source_type="metric",
            source_id="db_connections",
            content="DB connections: 100/100 (saturated) at 10:25Z",
            timestamp="2026-09-06T10:25:00Z",
            relevance=0.90,
        ),
        EvidenceItem(
            id="ev-003",
            source_type="log",
            source_id="log-abc",
            content="ERROR: connection timeout after 30000ms (db pool exhausted)",
            timestamp="2026-09-06T10:27:00Z",
            relevance=0.88,
        ),
    ]
    return state


@pytest.fixture
def state_with_hypotheses(state_with_evidence: InvestigationState) -> InvestigationState:
    """State with generated and validated hypotheses."""
    state = state_with_evidence.model_copy(deep=True)
    state.hypotheses = [
        Hypothesis(
            id="H1",
            description="DB connection pool exhaustion caused by deployment with db_pool_size=None",
            supporting_evidence=["ev-001", "ev-002", "ev-003"],
            validation_status=HypothesisValidationResult.SUPPORTED,
            confidence_score=86.0,
            rank=1,
        ),
        Hypothesis(
            id="H2",
            description="Traffic spike overloaded the database",
            supporting_evidence=[],
            contradicting_evidence=["ev-002"],
            validation_status=HypothesisValidationResult.UNSUPPORTED,
            confidence_score=15.0,
            rank=2,
        ),
        Hypothesis(
            id="H3",
            description="Memory leak in payment service causing slowdowns",
            supporting_evidence=[],
            validation_status=HypothesisValidationResult.UNSUPPORTED,
            confidence_score=10.0,
            rank=3,
        ),
    ]
    state.ranked_root_causes = [state.hypotheses[0]]
    state.primary_root_cause = state.hypotheses[0]
    state.overall_confidence = 86.0
    return state


@pytest.fixture
def complete_state(state_with_hypotheses: InvestigationState) -> InvestigationState:
    """A fully completed investigation state."""
    state = state_with_hypotheses.model_copy(deep=True)
    state.recommendations = [
        Recommendation(
            id="REC-001",
            action="Roll back deployment DEP-001 to previous version",
            reason="DEP-001 introduced db_pool_size=None, exhausting the connection pool",
            risk_level=RiskLevel.HIGH,
            expected_outcome="DB connection saturation resolved within 2-3 minutes",
            potential_impact="Brief service disruption during rollback (~30 seconds)",
            rollback_strategy="Re-deploy previous version using: kubectl rollout undo",
            supporting_evidence=["ev-001", "ev-002"],
            requires_approval=True,
        )
    ]
    state.requires_human_approval = True
    state.final_report = "## Investigation Complete\n\nRoot cause: DB pool exhaustion (86/100 confidence)"
    state.status = InvestigationStatus.COMPLETED
    return state


# ── Tool Mock Helpers ─────────────────────────────────────────


@pytest.fixture
def mock_db_session():
    """A mock AsyncSession for unit-testing tools without a real database."""
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    return session


@pytest.fixture
def deployment_result() -> dict:
    """Sample deployment tool result for mocking."""
    return {
        "success": True,
        "deployments": [
            {
                "deployment_id": "DEP-001",
                "service": "payment-api",
                "version": "v2.3.1",
                "commit_sha": "abc123def456",
                "status": "SUCCESS",
                "deployed_at": "2026-09-06T10:20:00+00:00",
                "deployed_by": "ci-bot",
                "metadata": {},
            }
        ],
        "count": 1,
        "service": "payment-api",
    }


@pytest.fixture
def log_result() -> dict:
    """Sample log search tool result for mocking."""
    return {
        "success": True,
        "logs": [
            {
                "id": "log-001",
                "timestamp": "2026-09-06T10:27:00+00:00",
                "level": "ERROR",
                "service": "payment-api",
                "message": "connection timeout after 30000ms (db pool exhausted)",
                "request_id": "req-abc",
                "metadata": {},
            }
        ],
        "summary": {
            "total": 1,
            "errors": 1,
            "warnings": 0,
            "info": 0,
            "notable_errors": ["connection timeout after 30000ms (db pool exhausted)"],
        },
    }


@pytest.fixture
def metric_result() -> dict:
    """Sample metrics tool result for mocking."""
    return {
        "success": True,
        "service": "payment-api",
        "metric_name": "db_connections",
        "data_points": [
            {"timestamp": "2026-09-06T10:25:00+00:00", "value": 100.0},
            {"timestamp": "2026-09-06T10:26:00+00:00", "value": 100.0},
        ],
        "statistics": {
            "min": 100.0,
            "max": 100.0,
            "avg": 100.0,
            "std_dev": 0.0,
            "count": 2,
            "first": 100.0,
            "last": 100.0,
            "change_pct": 0.0,
        },
        "anomalies": [],
        "spike_detected": False,
    }


# ── Ground Truth Fixtures ─────────────────────────────────────


@pytest.fixture
def ground_truth_inc001() -> dict:
    """Ground truth for the EVAL-001 / INC-001 benchmark incident."""
    return {
        "root_cause": "DB connection pool exhaustion",
        "acceptable_alternatives": [
            "database connection pool exhausted",
            "db_pool_size misconfiguration",
            "connection pool saturation",
        ],
        "required_evidence": [
            "deployment DEP-001",
            "db_pool_size",
            "connection timeout",
            "db connections 100",
        ],
        "expected_confidence_range": [70, 100],
    }
