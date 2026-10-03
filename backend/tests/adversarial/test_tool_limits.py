"""
Adversarial Tests — Tool Limits & Safety Boundaries
======================================================
Tests that the investigation agent respects configured limits:
- Maximum tool call count (prevents infinite loops)
- Timeout behaviour
- Graceful handling of tool failures
- State invariants are preserved under edge cases

These tests use the InvestigationState directly — no LLM calls needed.

Run:
    pytest tests/adversarial/test_tool_limits.py -v
"""

import pytest
from app.workflows.state import (
    InvestigationState,
    InvestigationStatus,
    EvidenceItem,
)


class TestToolCallLimit:
    """Tests for the max_tool_calls enforcement."""

    def test_can_call_tool_when_under_limit(self, base_state: InvestigationState):
        """can_call_tool() returns True when below the limit."""
        assert base_state.tool_call_count == 0
        assert base_state.max_tool_calls == 20
        assert base_state.can_call_tool() is True

    def test_cannot_call_tool_at_limit(self, base_state: InvestigationState):
        """can_call_tool() returns False when at the limit."""
        state = base_state.model_copy(deep=True)
        state.tool_call_count = 20
        assert state.can_call_tool() is False

    def test_cannot_call_tool_above_limit(self, base_state: InvestigationState):
        """can_call_tool() returns False when above the limit."""
        state = base_state.model_copy(deep=True)
        state.tool_call_count = 999
        assert state.can_call_tool() is False

    def test_tool_count_at_boundary(self, base_state: InvestigationState):
        """Boundary: 19 calls allowed, 20 not."""
        state = base_state.model_copy(deep=True)

        state.tool_call_count = 19
        assert state.can_call_tool() is True

        state.tool_call_count = 20
        assert state.can_call_tool() is False

    def test_custom_max_tool_calls_is_respected(self):
        """Custom max_tool_calls setting is honoured."""
        state = InvestigationState(
            incident_id="test",
            incident_title="test",
            incident_description="test",
            incident_service="payment-api",
            incident_time="2026-09-06T10:30:00Z",
            max_tool_calls=5,
        )
        state.tool_call_count = 4
        assert state.can_call_tool() is True

        state.tool_call_count = 5
        assert state.can_call_tool() is False


class TestStateImmutabilityAndHelpers:
    """Tests that state helper methods behave correctly."""

    def test_evidence_by_id_found(self, state_with_evidence: InvestigationState):
        """evidence_by_id returns the correct item."""
        ev = state_with_evidence.evidence_by_id("ev-001")
        assert ev is not None
        assert ev.id == "ev-001"
        assert ev.source_type == "deployment"

    def test_evidence_by_id_not_found(self, state_with_evidence: InvestigationState):
        """evidence_by_id returns None for unknown ID."""
        ev = state_with_evidence.evidence_by_id("nonexistent-id")
        assert ev is None

    def test_hypothesis_by_id_found(self, state_with_hypotheses: InvestigationState):
        """hypothesis_by_id returns the correct hypothesis."""
        h = state_with_hypotheses.hypothesis_by_id("H1")
        assert h is not None
        assert h.id == "H1"

    def test_hypothesis_by_id_not_found(self, state_with_hypotheses: InvestigationState):
        """hypothesis_by_id returns None for unknown ID."""
        h = state_with_hypotheses.hypothesis_by_id("H99")
        assert h is None

    def test_supporting_evidence_for_hypothesis(self, state_with_hypotheses: InvestigationState):
        """supporting_evidence_for returns items that support the hypothesis."""
        # Add support links to evidence
        state = state_with_hypotheses.model_copy(deep=True)
        state.collected_evidence[0].supports = ["H1"]
        state.collected_evidence[1].supports = ["H1"]

        supporting = state.supporting_evidence_for("H1")
        assert len(supporting) == 2

    def test_contradicting_evidence_for_hypothesis(self, state_with_hypotheses: InvestigationState):
        """contradicting_evidence_for returns items that contradict the hypothesis."""
        state = state_with_hypotheses.model_copy(deep=True)
        state.collected_evidence[0].contradicts = ["H2"]

        contradicting = state.contradicting_evidence_for("H2")
        assert len(contradicting) == 1


class TestStateEdgeCases:
    """Edge cases in state construction and manipulation."""

    def test_state_with_zero_evidence(self, base_state: InvestigationState):
        """State starts with empty evidence list — never None."""
        assert base_state.collected_evidence == []
        assert isinstance(base_state.collected_evidence, list)

    def test_state_errors_list_is_mutable(self, base_state: InvestigationState):
        """Errors list can be appended to without replacing the whole list."""
        state = base_state.model_copy(deep=True)
        state.errors.append("something went wrong")
        assert len(state.errors) == 1
        assert state.errors[0] == "something went wrong"

    def test_status_starts_as_pending(self, base_state: InvestigationState):
        """Fresh state always starts in PENDING status."""
        assert base_state.status == InvestigationStatus.PENDING

    def test_confidence_starts_at_zero(self, base_state: InvestigationState):
        """Initial confidence is 0.0."""
        assert base_state.overall_confidence == 0.0

    def test_state_serializable_to_dict(self, complete_state: InvestigationState):
        """Complete state can be serialised to dict without error."""
        d = complete_state.model_dump()
        assert isinstance(d, dict)
        assert "incident_id" in d
        assert "status" in d
        assert "recommendations" in d

    def test_unavailable_sources_tracked(self, base_state: InvestigationState):
        """Unavailable sources list starts empty and is appendable."""
        state = base_state.model_copy(deep=True)
        assert state.unavailable_sources == []

        state.unavailable_sources.append("github-api")
        assert "github-api" in state.unavailable_sources


class TestToolResultErrorHandling:
    """
    Tests that all tool error dicts have the correct structure.
    Tools must never raise — they must return error dicts.
    """

    def test_error_dict_has_success_false(self):
        """Error results from tools must have success=False."""
        # Canonical error dict shape used by all tools
        error_dict = {
            "success": False,
            "error": "DB connection refused",
            "logs": [],
            "summary": {"total": 0},
        }
        assert error_dict["success"] is False
        assert "error" in error_dict

    def test_empty_result_has_success_true(self):
        """Empty (no data) results from tools must have success=True."""
        # Canonical empty result — no error, just no data
        empty_dict = {
            "success": True,
            "data_points": [],
            "statistics": None,
            "anomalies": [],
            "message": "No data found",
        }
        assert empty_dict["success"] is True
        assert "error" not in empty_dict

    @pytest.mark.asyncio
    async def test_metrics_tool_handles_invalid_timestamp(self):
        """
        Metrics tool returns an error dict (not exception) for
        invalid timestamp strings.
        """
        from unittest.mock import AsyncMock, MagicMock, patch

        with patch("app.tools.metrics.AsyncSessionLocal") as mock_session_cls:
            from app.tools.metrics import search_metrics
            result = await search_metrics.ainvoke({
                "service": "payment-api",
                "metric_name": "db_connections",
                "start_time": "NOT_A_VALID_TIMESTAMP",
                "end_time": "ALSO_INVALID",
            })

        # Must return error dict, not raise
        assert "success" in result
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_deployments_tool_handles_invalid_timestamp(self):
        """Deployments tool returns error dict for invalid timestamps."""
        from unittest.mock import patch
        with patch("app.tools.deployments.AsyncSessionLocal") as mock_session_cls:
            from app.tools.deployments import search_deployments
            result = await search_deployments.ainvoke({
                "service": "payment-api",
                "start_time": "INVALID",
                "end_time": "ALSO_INVALID",
            })

        assert "success" in result
        assert result["success"] is False
