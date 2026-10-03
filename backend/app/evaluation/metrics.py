"""
Evaluation Metrics
===================
Pure functions for computing agent accuracy metrics.

These are extracted from scripts/run_evaluation.py so they can be:
1. Imported by the evaluation API endpoint
2. Unit tested without running the full evaluation script
3. Extended with new metrics without touching the script

All functions are deterministic and have no side effects.
"""

from __future__ import annotations

from typing import Any

from app.workflows.state import InvestigationState, HypothesisValidationResult


# ── Normalization ─────────────────────────────────────────────


def normalize_root_cause(rc: str) -> str:
    """
    Normalise a root cause string for fuzzy comparison.

    Lowercases, replaces spaces and hyphens with underscores.
    Example: "DB Pool Exhaustion" → "db_pool_exhaustion"
    """
    return rc.lower().replace(" ", "_").replace("-", "_")


def _keywords_match(candidate: str, target: str) -> bool:
    """
    Fuzzy keyword match — returns True if at least half the target
    keywords appear in the candidate string.

    This is intentionally lenient: the agent may phrase the root cause
    slightly differently from the ground truth.
    """
    keywords = normalize_root_cause(target).split("_")
    if not keywords:
        return False
    matches = sum(1 for kw in keywords if kw in normalize_root_cause(candidate))
    return matches >= max(1, len(keywords) // 2)


# ── Per-incident Metrics ──────────────────────────────────────


def compute_top1_accuracy(
    state: InvestigationState,
    ground_truth: dict[str, Any],
) -> bool:
    """
    True if the agent's #1 hypothesis matches an acceptable root cause.

    The ground_truth dict must have:
    - "root_cause": str — the canonical answer
    - "acceptable_alternatives": list[str] — other acceptable answers (optional)
    """
    primary = state.primary_root_cause
    if not primary:
        return False

    acceptable = [ground_truth["root_cause"]] + ground_truth.get("acceptable_alternatives", [])
    return any(_keywords_match(primary.description, alt) for alt in acceptable)


def compute_top3_accuracy(
    state: InvestigationState,
    ground_truth: dict[str, Any],
) -> bool:
    """
    True if any of the top-3 hypotheses matches an acceptable root cause.

    Used as a softer accuracy signal — the agent may rank the right answer
    second or third and still be useful.
    """
    acceptable = [ground_truth["root_cause"]] + ground_truth.get("acceptable_alternatives", [])
    for h in state.ranked_root_causes[:3]:
        if any(_keywords_match(h.description, alt) for alt in acceptable):
            return True
    return False


def compute_evidence_recall(
    state: InvestigationState,
    ground_truth: dict[str, Any],
) -> float:
    """
    Fraction of required evidence items that were found.

    Each required_evidence item is a short phrase. We check if ANY
    word from that phrase appears in the combined evidence text.

    Returns a float in [0.0, 1.0]. Returns 1.0 if no evidence is required.
    """
    required = ground_truth.get("required_evidence", [])
    if not required:
        return 1.0

    all_evidence_text = " ".join(e.content.lower() for e in state.collected_evidence)
    found = [
        req for req in required
        if any(word.lower() in all_evidence_text for word in req.split())
    ]
    return round(len(found) / len(required), 3)


def compute_unsupported_primary_claims(state: InvestigationState) -> int:
    """
    Count how many UNSUPPORTED hypotheses were ranked #1.

    An unsupported #1 ranking is a hallucination: the agent claimed
    a root cause it couldn't back with evidence.
    """
    return sum(
        1
        for h in state.hypotheses
        if h.validation_status == HypothesisValidationResult.UNSUPPORTED
        and h.rank == 1
    )


def compute_confidence_in_range(
    state: InvestigationState,
    ground_truth: dict[str, Any],
) -> bool:
    """True if the overall confidence score falls within the expected range."""
    expected_range = ground_truth.get("expected_confidence_range", [0, 100])
    return expected_range[0] <= state.overall_confidence <= expected_range[1]


# ── Aggregate Metrics ─────────────────────────────────────────


def compute_aggregate_metrics(per_incident_results: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Compute aggregate metrics from a list of per-incident result dicts.

    Each dict must have the fields produced by evaluate_single().
    Error results (those with an "error" key) are excluded.
    """
    valid = [r for r in per_incident_results if "error" not in r]
    n = len(valid)

    if n == 0:
        return {"error": "No valid results to aggregate", "incidents_tested": 0}

    return {
        "incidents_tested": n,
        "top1_accuracy": round(sum(r["top1_correct"] for r in valid) / n, 3),
        "top3_accuracy": round(sum(r["top3_correct"] for r in valid) / n, 3),
        "avg_evidence_recall": round(sum(r["evidence_recall"] for r in valid) / n, 3),
        "avg_confidence": round(sum(r["confidence_score"] for r in valid) / n, 1),
        "avg_tool_calls": round(sum(r.get("tool_calls", 0) for r in valid) / n, 1),
        "avg_hypotheses": round(sum(r.get("hypotheses_count", 0) for r in valid) / n, 1),
        "avg_duration_seconds": round(
            sum(r.get("duration_seconds", 0) for r in valid) / n, 1
        ),
        "unsupported_primary_claim_rate": round(
            sum(r.get("unsupported_primary_claims", 0) for r in valid) / max(n, 1), 3
        ),
        "human_escalation_rate": round(
            sum(r.get("required_human_approval", False) for r in valid) / n, 3
        ),
    }


# ── Full Single-Incident Evaluation ──────────────────────────


def evaluate_single(
    state: InvestigationState,
    ground_truth: dict[str, Any],
    incident_def: dict[str, Any],
    duration_seconds: float = 0.0,
) -> dict[str, Any]:
    """
    Evaluate one investigation result against its ground truth.

    This is the canonical per-incident evaluation function used by
    both scripts/run_evaluation.py and the evaluation harness.

    Returns a dict that can be serialised to results.json.
    """
    top1 = compute_top1_accuracy(state, ground_truth)
    top3 = compute_top3_accuracy(state, ground_truth)
    recall = compute_evidence_recall(state, ground_truth)
    unsupported = compute_unsupported_primary_claims(state)
    confidence_ok = compute_confidence_in_range(state, ground_truth)

    primary = state.primary_root_cause

    return {
        "incident_id": incident_def.get("id", "UNKNOWN"),
        "ground_truth_id": incident_def.get("ground_truth_id", ""),
        "top1_correct": top1,
        "top3_correct": top3,
        "evidence_recall": recall,
        "confidence_score": state.overall_confidence,
        "confidence_in_expected_range": confidence_ok,
        "hypotheses_count": len(state.hypotheses),
        "evidence_count": len(state.collected_evidence),
        "tool_calls": state.tool_call_count,
        "required_human_approval": state.requires_human_approval,
        "unsupported_primary_claims": unsupported,
        "identified_root_cause": primary.description if primary else "NONE",
        "expected_root_cause": ground_truth.get("root_cause", "UNKNOWN"),
        "status": str(state.status),
        "duration_seconds": round(duration_seconds, 1),
    }
