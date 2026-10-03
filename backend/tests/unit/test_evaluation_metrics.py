"""
Unit Tests — Evaluation Metrics
==================================
Tests the pure metric functions in app.evaluation.metrics.

These functions are deterministic — no DB, no LLM, no mocking needed.
We pass constructed InvestigationState objects directly.

Run:
    pytest tests/unit/test_evaluation_metrics.py -v
"""

import pytest
from app.evaluation.metrics import (
    normalize_root_cause,
    compute_top1_accuracy,
    compute_top3_accuracy,
    compute_evidence_recall,
    compute_unsupported_primary_claims,
    compute_confidence_in_range,
    compute_aggregate_metrics,
    evaluate_single,
)


# ── normalize_root_cause ──────────────────────────────────────


class TestNormalizeRootCause:
    def test_lowercases(self):
        assert normalize_root_cause("DB Pool Exhaustion") == "db_pool_exhaustion"

    def test_replaces_spaces(self):
        assert normalize_root_cause("connection pool saturation") == "connection_pool_saturation"

    def test_replaces_hyphens(self):
        assert normalize_root_cause("out-of-memory") == "out_of_memory"

    def test_already_normalized(self):
        assert normalize_root_cause("db_pool") == "db_pool"


# ── compute_top1_accuracy ─────────────────────────────────────


class TestTop1Accuracy:
    def test_correct_primary(self, state_with_hypotheses, ground_truth_inc001):
        """Returns True when primary hypothesis matches ground truth."""
        result = compute_top1_accuracy(state_with_hypotheses, ground_truth_inc001)
        assert result is True

    def test_no_primary(self, analyzed_state, ground_truth_inc001):
        """Returns False when primary_root_cause is None."""
        assert analyzed_state.primary_root_cause is None
        result = compute_top1_accuracy(analyzed_state, ground_truth_inc001)
        assert result is False

    def test_wrong_primary(self, state_with_hypotheses, ground_truth_inc001):
        """Returns False when primary hypothesis doesn't match."""
        state = state_with_hypotheses.model_copy(deep=True)
        state.primary_root_cause.description = "memory leak in payment service"
        result = compute_top1_accuracy(state, ground_truth_inc001)
        assert result is False

    def test_accepts_alternative(self, state_with_hypotheses):
        """Accepts an alternative root cause description."""
        from app.workflows.state import Hypothesis, HypothesisValidationResult
        state = state_with_hypotheses.model_copy(deep=True)
        state.primary_root_cause = Hypothesis(
            id="H1",
            description="Database connection pool saturation",
            validation_status=HypothesisValidationResult.SUPPORTED,
            confidence_score=85.0,
            rank=1,
        )
        gt = {
            "root_cause": "DB connection pool exhaustion",
            "acceptable_alternatives": [
                "connection pool saturation",
                "db connections maxed out",
            ],
        }
        result = compute_top1_accuracy(state, gt)
        assert result is True


# ── compute_top3_accuracy ─────────────────────────────────────


class TestTop3Accuracy:
    def test_correct_in_top3(self, state_with_hypotheses, ground_truth_inc001):
        """Returns True when correct answer appears in top-3."""
        result = compute_top3_accuracy(state_with_hypotheses, ground_truth_inc001)
        assert result is True

    def test_correct_only_in_rank2(self, state_with_hypotheses, ground_truth_inc001):
        """Returns True even when correct answer is rank 2 (not top-1)."""
        state = state_with_hypotheses.model_copy(deep=True)
        # Flip ranks: make H2 the top-1, keep H1 (correct) at rank 2
        state.ranked_root_causes = [state.hypotheses[1], state.hypotheses[0]]
        state.primary_root_cause = state.hypotheses[1]
        result = compute_top3_accuracy(state, ground_truth_inc001)
        assert result is True

    def test_not_in_top3(self, state_with_hypotheses):
        """Returns False when none of the top-3 match."""
        gt = {
            "root_cause": "traffic spike",
            "acceptable_alternatives": [],
        }
        result = compute_top3_accuracy(state_with_hypotheses, gt)
        assert result is False

    def test_empty_ranked_causes(self, base_state, ground_truth_inc001):
        """Returns False when no ranked root causes exist."""
        result = compute_top3_accuracy(base_state, ground_truth_inc001)
        assert result is False


# ── compute_evidence_recall ───────────────────────────────────


class TestEvidenceRecall:
    def test_all_evidence_found(self, state_with_evidence):
        """Returns 1.0 when all required evidence is present."""
        # Ground truth items that are actually present in state_with_evidence content:
        # - ev-001 content has 'deployment' and 'DEP-001' and 'abc123'
        # - ev-002 content has 'db connections' and '100'
        # - ev-003 content has 'connection timeout'
        gt = {
            "root_cause": "DB connection pool exhaustion",
            "required_evidence": [
                "deployment DEP-001",
                "DB connections",
                "connection timeout",
            ],
        }
        recall = compute_evidence_recall(state_with_evidence, gt)
        assert recall == 1.0

    def test_partial_evidence(self, base_state, ground_truth_inc001):
        """Returns fraction when only some evidence is found."""
        recall = compute_evidence_recall(base_state, ground_truth_inc001)
        assert recall == 0.0  # base_state has no evidence

    def test_no_requirements(self, base_state):
        """Returns 1.0 when no evidence is required."""
        gt = {"root_cause": "anything", "required_evidence": []}
        recall = compute_evidence_recall(base_state, gt)
        assert recall == 1.0

    def test_missing_required_key(self, base_state):
        """Returns 1.0 when required_evidence key is absent from ground truth."""
        gt = {"root_cause": "anything"}
        recall = compute_evidence_recall(base_state, gt)
        assert recall == 1.0


# ── compute_unsupported_primary_claims ────────────────────────


class TestUnsupportedClaims:
    def test_no_unsupported_at_rank1(self, state_with_hypotheses):
        """Returns 0 when rank-1 hypothesis is SUPPORTED."""
        count = compute_unsupported_primary_claims(state_with_hypotheses)
        assert count == 0

    def test_unsupported_at_rank1(self, state_with_hypotheses):
        """Returns 1 when rank-1 hypothesis is UNSUPPORTED."""
        from app.workflows.state import HypothesisValidationResult
        state = state_with_hypotheses.model_copy(deep=True)
        state.hypotheses[0].validation_status = HypothesisValidationResult.UNSUPPORTED
        count = compute_unsupported_primary_claims(state)
        assert count == 1

    def test_unsupported_at_rank2_not_counted(self, state_with_hypotheses):
        """UNSUPPORTED at rank 2+ doesn't count — only rank 1 matters."""
        # H2 in fixture is UNSUPPORTED at rank 2 — should NOT be counted
        count = compute_unsupported_primary_claims(state_with_hypotheses)
        assert count == 0


# ── compute_confidence_in_range ───────────────────────────────


class TestConfidenceInRange:
    def test_within_range(self, complete_state, ground_truth_inc001):
        """Returns True when confidence is within expected range."""
        result = compute_confidence_in_range(complete_state, ground_truth_inc001)
        assert result is True  # 86.0 is in [70, 100]

    def test_below_range(self, complete_state):
        """Returns False when confidence is below expected range."""
        gt = {"root_cause": "x", "expected_confidence_range": [90, 100]}
        result = compute_confidence_in_range(complete_state, gt)
        assert result is False  # 86.0 < 90

    def test_default_range_always_passes(self, complete_state):
        """Default range [0, 100] always passes."""
        gt = {"root_cause": "x"}
        result = compute_confidence_in_range(complete_state, gt)
        assert result is True


# ── compute_aggregate_metrics ─────────────────────────────────


class TestAggregateMetrics:
    def test_all_correct(self):
        per_incident = [
            {
                "top1_correct": True,
                "top3_correct": True,
                "evidence_recall": 1.0,
                "confidence_score": 90.0,
                "tool_calls": 15,
                "hypotheses_count": 3,
                "duration_seconds": 45.0,
                "required_human_approval": True,
                "unsupported_primary_claims": 0,
            },
            {
                "top1_correct": True,
                "top3_correct": True,
                "evidence_recall": 0.8,
                "confidence_score": 75.0,
                "tool_calls": 12,
                "hypotheses_count": 3,
                "duration_seconds": 38.0,
                "required_human_approval": False,
                "unsupported_primary_claims": 0,
            },
        ]
        metrics = compute_aggregate_metrics(per_incident)
        assert metrics["top1_accuracy"] == 1.0
        assert metrics["top3_accuracy"] == 1.0
        assert metrics["avg_evidence_recall"] == 0.9
        assert metrics["incidents_tested"] == 2

    def test_excludes_error_results(self):
        """Error results (those with 'error' key) are excluded from aggregate."""
        per_incident = [
            {
                "top1_correct": True,
                "top3_correct": True,
                "evidence_recall": 1.0,
                "confidence_score": 90.0,
                "tool_calls": 10,
                "hypotheses_count": 3,
                "duration_seconds": 30.0,
                "required_human_approval": False,
                "unsupported_primary_claims": 0,
            },
            {"error": "Investigation timed out"},
        ]
        metrics = compute_aggregate_metrics(per_incident)
        assert metrics["incidents_tested"] == 1  # error excluded
        assert metrics["top1_accuracy"] == 1.0

    def test_empty_results(self):
        """Returns error dict when no valid results."""
        metrics = compute_aggregate_metrics([])
        assert "error" in metrics
        assert metrics["incidents_tested"] == 0

    def test_all_errors(self):
        """Returns error dict when all results are errors."""
        per_incident = [
            {"error": "timeout"},
            {"error": "crash"},
        ]
        metrics = compute_aggregate_metrics(per_incident)
        assert "error" in metrics


# ── evaluate_single ───────────────────────────────────────────


class TestEvaluateSingle:
    def test_complete_state_fields(self, complete_state, ground_truth_inc001):
        """evaluate_single returns all required fields."""
        incident_def = {"id": "EVAL-001", "ground_truth_id": "INC-001"}
        result = evaluate_single(complete_state, ground_truth_inc001, incident_def, 42.5)

        required_fields = [
            "incident_id", "top1_correct", "top3_correct",
            "evidence_recall", "confidence_score", "hypotheses_count",
            "evidence_count", "tool_calls", "required_human_approval",
            "identified_root_cause", "expected_root_cause", "duration_seconds",
        ]
        for field in required_fields:
            assert field in result, f"Missing field: {field}"

    def test_duration_stored(self, complete_state, ground_truth_inc001):
        """Duration seconds is passed through correctly."""
        incident_def = {"id": "EVAL-001"}
        result = evaluate_single(complete_state, ground_truth_inc001, incident_def, 99.7)
        assert result["duration_seconds"] == 99.7
