"""
RootTrace Evaluation Script
=============================
Runs the AI investigation agent against known incidents and measures accuracy.

🎓 EVALUATION METHODOLOGY:
1. Load each benchmark incident (from ground_truth.json)
2. Create the incident in the system (same as a real user would)
3. Run the investigation agent (agent never sees ground_truth.json)
4. Compare results:
   - Did the agent identify the correct root cause?
   - Did it retrieve the required evidence?
   - What confidence score did it assign?
   - Were there any unsupported claims?
5. Calculate aggregate metrics

This is the standard approach for evaluating RAG + agentic systems.
The agent is evaluated on held-out cases — it never sees the ground truth.

Run: python scripts/run_evaluation.py
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.workflows.investigation_graph import investigation_graph
from app.workflows.state import InvestigationState, HypothesisValidationResult

# ── Load ground truth (ONLY used for evaluation, never passed to agent) ──
GROUND_TRUTH_FILE = Path(__file__).parent.parent.parent / "incident-lab" / "evaluation" / "ground_truth.json"
RESULTS_FILE = Path(__file__).parent.parent.parent / "incident-lab" / "evaluation" / "results.json"
REPORT_FILE = Path(__file__).parent.parent.parent / "incident-lab" / "evaluation" / "report.md"


# Benchmark incident definitions (what the agent receives — NO ground truth)
BENCHMARK_INCIDENTS = [
    {
        "id": "EVAL-001",
        "ground_truth_id": "INC-001",
        "title": "Payment API latency increased 300% after latest deployment",
        "description": "Users are experiencing significant payment processing delays. "
                       "The issue started approximately 10 minutes after the latest deployment. "
                       "API response times have gone from ~120ms to over 600ms. "
                       "Some requests are timing out entirely.",
        "service": "payment-api",
        "incident_time": "2026-09-06T10:30:00Z",
    },
    {
        "id": "EVAL-002",
        "ground_truth_id": "INC-002",
        "title": "Payment history endpoint is extremely slow",
        "description": "The GET /payments/history endpoint is returning responses in 1-3 seconds "
                       "instead of the expected 30-50ms. Only the history endpoint is affected. "
                       "Other payment endpoints appear normal.",
        "service": "payment-api",
        "incident_time": "2026-09-07T15:00:00Z",
    },
    {
        "id": "EVAL-003",
        "ground_truth_id": "INC-003",
        "title": "Payment API memory usage climbing — OOM imminent",
        "description": "Memory usage on payment-api pods has been climbing continuously for 6 hours. "
                       "Started at 40% after morning deployment, now at 92% and still rising. "
                       "Pod restart expected within 30 minutes.",
        "service": "payment-api",
        "incident_time": "2026-09-08T15:00:00Z",
    },
    {
        "id": "EVAL-004",
        "ground_truth_id": "INC-004",
        "title": "Payment processing latency spiking — correlated with fraud service",
        "description": "Payment creation latency has increased from 150ms to 8+ seconds. "
                       "The fraud service appears to be slow. "
                       "Database metrics look normal. "
                       "The issue affects all payment creation requests.",
        "service": "payment-api",
        "incident_time": "2026-09-09T13:10:00Z",
    },
    {
        "id": "EVAL-005",
        "ground_truth_id": "INC-005",
        "title": "All authenticated API requests returning 401 Unauthorized",
        "description": "Since the latest deployment, all authenticated endpoints return 401. "
                       "Unauthenticated endpoints (health check) are working fine. "
                       "Users cannot access any payment data. "
                       "Tokens were valid before deployment.",
        "service": "payment-api",
        "incident_time": "2026-09-10T17:05:00Z",
    },
]


def normalize_root_cause(rc: str) -> str:
    """Normalize root cause strings for comparison."""
    return rc.lower().replace(" ", "_").replace("-", "_")


def evaluate_single(
    incident_result: InvestigationState,
    ground_truth: dict,
    incident_def: dict,
) -> dict:
    """Evaluate a single investigation result against ground truth."""

    expected_rc = normalize_root_cause(ground_truth["root_cause"])
    expected_confidence_range = ground_truth.get("expected_confidence_range", [0, 100])
    required_evidence = ground_truth.get("required_evidence", [])

    # Check root cause accuracy
    primary = incident_result.primary_root_cause
    top1_correct = False
    top3_correct = False

    if primary:
        primary_rc = normalize_root_cause(primary.description)
        # Fuzzy match: check if any expected root cause keyword is in the identified one
        acceptable = [ground_truth["root_cause"]] + ground_truth.get("acceptable_alternatives", [])
        for alt in acceptable:
            keywords = normalize_root_cause(alt).split("_")
            if sum(1 for kw in keywords if kw in primary_rc) >= len(keywords) // 2:
                top1_correct = True
                break

    for h in incident_result.ranked_root_causes[:3]:
        h_rc = normalize_root_cause(h.description)
        acceptable = [ground_truth["root_cause"]] + ground_truth.get("acceptable_alternatives", [])
        for alt in acceptable:
            keywords = normalize_root_cause(alt).split("_")
            if sum(1 for kw in keywords if kw in h_rc) >= len(keywords) // 2:
                top3_correct = True
                break

    # Evidence recall: check if required evidence was collected
    all_evidence_text = " ".join([
        e.content.lower() for e in incident_result.collected_evidence
    ])
    evidence_found = [
        req for req in required_evidence
        if any(word.lower() in all_evidence_text for word in req.split())
    ]
    evidence_recall = len(evidence_found) / len(required_evidence) if required_evidence else 1.0

    # Confidence in range
    confidence_in_range = (
        expected_confidence_range[0] <= incident_result.overall_confidence <= expected_confidence_range[1]
    )

    # Unsupported claim detection
    supported_hypotheses = [
        h for h in incident_result.hypotheses
        if h.validation_status == HypothesisValidationResult.SUPPORTED
    ]
    unsupported_claims = [
        h for h in incident_result.hypotheses
        if h.validation_status in (
            HypothesisValidationResult.UNSUPPORTED,
        ) and h.rank == 1  # Only flag if ranked #1
    ]

    return {
        "incident_id": incident_def["id"],
        "ground_truth_id": incident_def["ground_truth_id"],
        "top1_correct": top1_correct,
        "top3_correct": top3_correct,
        "evidence_recall": round(evidence_recall, 3),
        "confidence_score": incident_result.overall_confidence,
        "confidence_in_expected_range": confidence_in_range,
        "hypotheses_count": len(incident_result.hypotheses),
        "evidence_count": len(incident_result.collected_evidence),
        "tool_calls": incident_result.tool_call_count,
        "required_human_approval": incident_result.requires_human_approval,
        "unsupported_primary_claims": len(unsupported_claims),
        "identified_root_cause": primary.description if primary else "NONE",
        "expected_root_cause": ground_truth["root_cause"],
        "status": incident_result.status,
    }


async def run_evaluation():
    """Run the full evaluation benchmark."""

    print("\n" + "="*60)
    print("  ROOTTRACE EVALUATION BENCHMARK")
    print("="*60)

    # Load ground truth
    if not GROUND_TRUTH_FILE.exists():
        print(f"ERROR: Ground truth file not found: {GROUND_TRUTH_FILE}")
        sys.exit(1)

    ground_truth = json.loads(GROUND_TRUTH_FILE.read_text())

    results = []
    print(f"\nRunning {len(BENCHMARK_INCIDENTS)} benchmark incidents...\n")

    for incident_def in BENCHMARK_INCIDENTS:
        gt_id = incident_def["ground_truth_id"]
        gt = ground_truth.get(gt_id, {})

        print(f"  🔍 {incident_def['id']}: {incident_def['title'][:60]}...")

        # Create initial state (NO ground truth passed to agent)
        initial_state = InvestigationState(
            incident_id=str(uuid.uuid4()),
            incident_title=incident_def["title"],
            incident_description=incident_def["description"],
            incident_service=incident_def["service"],
            incident_time=incident_def["incident_time"],
        )

        try:
            start = datetime.now(timezone.utc)
            final_state = await investigation_graph.ainvoke(initial_state)
            duration = (datetime.now(timezone.utc) - start).total_seconds()

            result = evaluate_single(final_state, gt, incident_def)
            result["duration_seconds"] = round(duration, 1)
            results.append(result)

            status = "✅" if result["top1_correct"] else ("⚠️ " if result["top3_correct"] else "❌")
            print(f"    {status} Top-1: {result['top1_correct']}, "
                  f"Confidence: {result['confidence_score']:.0f}/100, "
                  f"Duration: {duration:.0f}s")

        except Exception as e:
            print(f"    ❌ FAILED: {e}")
            results.append({
                "incident_id": incident_def["id"],
                "top1_correct": False,
                "top3_correct": False,
                "error": str(e),
            })

    # ── Aggregate Metrics ─────────────────────────────────────
    valid_results = [r for r in results if "error" not in r]
    n = len(valid_results)

    if n == 0:
        print("\nERROR: No valid results to aggregate")
        return

    metrics = {
        "benchmark_date": datetime.now(timezone.utc).isoformat(),
        "incidents_tested": n,
        "top1_accuracy": round(sum(r["top1_correct"] for r in valid_results) / n, 3),
        "top3_accuracy": round(sum(r["top3_correct"] for r in valid_results) / n, 3),
        "avg_evidence_recall": round(sum(r["evidence_recall"] for r in valid_results) / n, 3),
        "avg_confidence": round(sum(r["confidence_score"] for r in valid_results) / n, 1),
        "avg_tool_calls": round(sum(r["tool_calls"] for r in valid_results) / n, 1),
        "avg_hypotheses": round(sum(r["hypotheses_count"] for r in valid_results) / n, 1),
        "avg_duration_seconds": round(sum(r.get("duration_seconds", 0) for r in valid_results) / n, 1),
        "unsupported_primary_claim_rate": round(
            sum(r["unsupported_primary_claims"] for r in valid_results) / max(n, 1), 3
        ),
        "human_escalation_rate": round(
            sum(r["required_human_approval"] for r in valid_results) / n, 3
        ),
        "per_incident": results,
    }

    # Save results
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(metrics, indent=2))
    print(f"\n  Results saved to: {RESULTS_FILE}")

    # Generate report
    report = f"""# RootTrace Evaluation Report

**Date:** {metrics['benchmark_date']}
**Incidents Tested:** {metrics['incidents_tested']}

## Summary Metrics

| Metric | Value | Target |
|--------|-------|--------|
| Root Cause Top-1 Accuracy | {metrics['top1_accuracy']*100:.1f}% | ≥80% |
| Root Cause Top-3 Accuracy | {metrics['top3_accuracy']*100:.1f}% | ≥95% |
| Evidence Recall | {metrics['avg_evidence_recall']*100:.1f}% | ≥85% |
| Avg Confidence Score | {metrics['avg_confidence']:.1f}/100 | — |
| Avg Tool Calls | {metrics['avg_tool_calls']:.1f} | ≤{20} |
| Avg Hypotheses Generated | {metrics['avg_hypotheses']:.1f} | ≥3 |
| Unsupported Claim Rate | {metrics['unsupported_primary_claim_rate']*100:.1f}% | ≤5% |
| Human Escalation Rate | {metrics['human_escalation_rate']*100:.1f}% | — |
| Avg Investigation Duration | {metrics['avg_duration_seconds']:.0f}s | ≤300s |

## Per-Incident Results

| Incident | Title | Top-1 | Top-3 | Confidence | Duration |
|----------|-------|-------|-------|------------|----------|
"""
    for r in results:
        if "error" not in r:
            report += (
                f"| {r['incident_id']} | "
                f"{r['ground_truth_id']} | "
                f"{'✅' if r['top1_correct'] else '❌'} | "
                f"{'✅' if r['top3_correct'] else '❌'} | "
                f"{r['confidence_score']:.0f}/100 | "
                f"{r.get('duration_seconds', '?')}s |\n"
            )

    REPORT_FILE.write_text(report)
    print(f"  Report saved to: {REPORT_FILE}")

    print("\n" + "="*60)
    print("  EVALUATION RESULTS")
    print("="*60)
    print(f"  Top-1 Accuracy:     {metrics['top1_accuracy']*100:.1f}%")
    print(f"  Top-3 Accuracy:     {metrics['top3_accuracy']*100:.1f}%")
    print(f"  Evidence Recall:    {metrics['avg_evidence_recall']*100:.1f}%")
    print(f"  Avg Confidence:     {metrics['avg_confidence']:.1f}/100")
    print(f"  Unsupported Claims: {metrics['unsupported_primary_claim_rate']*100:.1f}%")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(run_evaluation())
