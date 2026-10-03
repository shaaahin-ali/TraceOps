"""
Evaluation Harness
===================
Wraps the investigation graph for benchmark evaluation.

Responsibilities:
- Loads ground truth from the JSON file (never passed to the agent)
- Runs the agent on each benchmark incident
- Calls the metric functions from metrics.py
- Saves results to the standard output files

This is a thin coordinator — the actual investigation logic lives in
investigation_graph.py and the metric logic lives in metrics.py.

Usage:
    harness = EvaluationHarness()
    results = await harness.run()
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from app.evaluation.metrics import evaluate_single, compute_aggregate_metrics
from app.workflows.investigation_graph import investigation_graph
from app.workflows.state import InvestigationState

logger = structlog.get_logger(__name__)

# ── File Paths ────────────────────────────────────────────────

_EVAL_DIR = Path(__file__).parent.parent.parent.parent / "incident-lab" / "evaluation"
GROUND_TRUTH_FILE = _EVAL_DIR / "ground_truth.json"
RESULTS_FILE = _EVAL_DIR / "results.json"
REPORT_FILE = _EVAL_DIR / "report.md"

# ── Benchmark Incidents ───────────────────────────────────────
# What the agent receives — NO ground truth information here.

BENCHMARK_INCIDENTS: list[dict[str, Any]] = [
    {
        "id": "EVAL-001",
        "ground_truth_id": "INC-001",
        "title": "Payment API latency increased 300% after latest deployment",
        "description": (
            "Users are experiencing significant payment processing delays. "
            "The issue started approximately 10 minutes after the latest deployment. "
            "API response times have gone from ~120ms to over 600ms. "
            "Some requests are timing out entirely."
        ),
        "service": "payment-api",
        "incident_time": "2026-09-06T10:30:00Z",
    },
    {
        "id": "EVAL-002",
        "ground_truth_id": "INC-002",
        "title": "Payment history endpoint is extremely slow",
        "description": (
            "The GET /payments/history endpoint is returning responses in 1-3 seconds "
            "instead of the expected 30-50ms. Only the history endpoint is affected. "
            "Other payment endpoints appear normal."
        ),
        "service": "payment-api",
        "incident_time": "2026-09-07T15:00:00Z",
    },
    {
        "id": "EVAL-003",
        "ground_truth_id": "INC-003",
        "title": "Payment API memory usage climbing — OOM imminent",
        "description": (
            "Memory usage on payment-api pods has been climbing continuously for 6 hours. "
            "Started at 40% after morning deployment, now at 92% and still rising. "
            "Pod restart expected within 30 minutes."
        ),
        "service": "payment-api",
        "incident_time": "2026-09-08T15:00:00Z",
    },
    {
        "id": "EVAL-004",
        "ground_truth_id": "INC-004",
        "title": "Payment processing latency spiking — correlated with fraud service",
        "description": (
            "Payment creation latency has increased from 150ms to 8+ seconds. "
            "The fraud service appears to be slow. "
            "Database metrics look normal. "
            "The issue affects all payment creation requests."
        ),
        "service": "payment-api",
        "incident_time": "2026-09-09T13:10:00Z",
    },
    {
        "id": "EVAL-005",
        "ground_truth_id": "INC-005",
        "title": "All authenticated API requests returning 401 Unauthorized",
        "description": (
            "Since the latest deployment, all authenticated endpoints return 401. "
            "Unauthenticated endpoints (health check) are working fine. "
            "Users cannot access any payment data. "
            "Tokens were valid before deployment."
        ),
        "service": "payment-api",
        "incident_time": "2026-09-10T17:05:00Z",
    },
]


class EvaluationHarness:
    """
    Runs the RootTrace agent against benchmark incidents and
    measures accuracy against held-out ground truth.

    The agent NEVER sees the ground_truth.json file — it only
    receives the incident description as a real user would.
    """

    def __init__(
        self,
        ground_truth_file: Path = GROUND_TRUTH_FILE,
        results_file: Path = RESULTS_FILE,
        report_file: Path = REPORT_FILE,
    ) -> None:
        self.ground_truth_file = ground_truth_file
        self.results_file = results_file
        self.report_file = report_file
        self._ground_truth: dict[str, Any] = {}

    def _load_ground_truth(self) -> None:
        if not self.ground_truth_file.exists():
            raise FileNotFoundError(
                f"Ground truth file not found: {self.ground_truth_file}\n"
                "Run scripts/seed_data.py to create it."
            )
        self._ground_truth = json.loads(self.ground_truth_file.read_text())

    async def _run_single(self, incident_def: dict[str, Any]) -> dict[str, Any]:
        """Run one benchmark incident through the investigation graph."""
        gt_id = incident_def["ground_truth_id"]
        gt = self._ground_truth.get(gt_id, {})

        initial_state = InvestigationState(
            incident_id=str(uuid.uuid4()),
            incident_title=incident_def["title"],
            incident_description=incident_def["description"],
            incident_service=incident_def["service"],
            incident_time=incident_def["incident_time"],
        )

        start = datetime.now(timezone.utc)
        final_state = await investigation_graph.ainvoke(initial_state)
        duration = (datetime.now(timezone.utc) - start).total_seconds()

        result = evaluate_single(final_state, gt, incident_def, duration_seconds=duration)
        logger.info(
            "harness.incident_complete",
            incident_id=incident_def["id"],
            top1=result["top1_correct"],
            confidence=result["confidence_score"],
            duration=duration,
        )
        return result

    async def run(
        self,
        incidents: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Run the full evaluation benchmark.

        Args:
            incidents: Override benchmark incidents (useful for testing subsets).

        Returns:
            Aggregate metrics dict with per_incident breakdown.
        """
        self._load_ground_truth()
        incidents = incidents or BENCHMARK_INCIDENTS
        per_incident: list[dict[str, Any]] = []

        for incident_def in incidents:
            logger.info("harness.running", incident_id=incident_def["id"])
            try:
                result = await self._run_single(incident_def)
                per_incident.append(result)
            except Exception as exc:
                logger.error(
                    "harness.incident_failed",
                    incident_id=incident_def["id"],
                    error=str(exc),
                )
                per_incident.append({
                    "incident_id": incident_def["id"],
                    "top1_correct": False,
                    "top3_correct": False,
                    "error": str(exc),
                })

        aggregate = compute_aggregate_metrics(per_incident)
        output = {
            "benchmark_date": datetime.now(timezone.utc).isoformat(),
            **aggregate,
            "per_incident": per_incident,
        }

        # Persist results
        self.results_file.parent.mkdir(parents=True, exist_ok=True)
        self.results_file.write_text(json.dumps(output, indent=2))
        logger.info("harness.results_saved", path=str(self.results_file))

        return output

    def generate_report(self, metrics: dict[str, Any]) -> str:
        """Generate a Markdown benchmark report from aggregate metrics."""
        n = metrics.get("incidents_tested", 0)
        report = f"""# RootTrace Evaluation Report

**Date:** {metrics.get("benchmark_date", "—")}
**Incidents Tested:** {n}

## Summary Metrics

| Metric | Value | Target |
|--------|-------|--------|
| Root Cause Top-1 Accuracy | {metrics.get("top1_accuracy", 0)*100:.1f}% | ≥80% |
| Root Cause Top-3 Accuracy | {metrics.get("top3_accuracy", 0)*100:.1f}% | ≥95% |
| Evidence Recall | {metrics.get("avg_evidence_recall", 0)*100:.1f}% | ≥85% |
| Avg Confidence Score | {metrics.get("avg_confidence", 0):.1f}/100 | — |
| Avg Tool Calls | {metrics.get("avg_tool_calls", 0):.1f} | ≤20 |
| Avg Hypotheses Generated | {metrics.get("avg_hypotheses", 0):.1f} | ≥3 |
| Unsupported Claim Rate | {metrics.get("unsupported_primary_claim_rate", 0)*100:.1f}% | ≤5% |
| Human Escalation Rate | {metrics.get("human_escalation_rate", 0)*100:.1f}% | — |
| Avg Investigation Duration | {metrics.get("avg_duration_seconds", 0):.0f}s | ≤300s |

## Per-Incident Results

| Incident | GT ID | Top-1 | Top-3 | Confidence | Duration |
|----------|-------|-------|-------|------------|----------|
"""
        for r in metrics.get("per_incident", []):
            if "error" not in r:
                report += (
                    f"| {r['incident_id']} | "
                    f"{r.get('ground_truth_id', '—')} | "
                    f"{'✅' if r['top1_correct'] else '❌'} | "
                    f"{'✅' if r['top3_correct'] else '❌'} | "
                    f"{r['confidence_score']:.0f}/100 | "
                    f"{r.get('duration_seconds', '?')}s |\n"
                )

        if self.report_file:
            self.report_file.write_text(report)
            logger.info("harness.report_saved", path=str(self.report_file))

        return report
