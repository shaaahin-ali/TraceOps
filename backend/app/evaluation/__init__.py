"""
Evaluation Package
===================
Agent accuracy measurement and benchmarking.

Modules:
    metrics  — pure metric computation functions
    harness  — EvaluationHarness class for running benchmarks
"""

from app.evaluation.metrics import (
    evaluate_single,
    compute_aggregate_metrics,
    compute_top1_accuracy,
    compute_top3_accuracy,
    compute_evidence_recall,
    compute_unsupported_primary_claims,
)
from app.evaluation.harness import EvaluationHarness, BENCHMARK_INCIDENTS

__all__ = [
    "evaluate_single",
    "compute_aggregate_metrics",
    "compute_top1_accuracy",
    "compute_top3_accuracy",
    "compute_evidence_recall",
    "compute_unsupported_primary_claims",
    "EvaluationHarness",
    "BENCHMARK_INCIDENTS",
]
