"""
RootTrace Agent Nodes
======================
Exposes the LangGraph node functions for the investigation workflow.

Each node is a pure async function:
  - Input: InvestigationState
  - Output: dict of state updates

Nodes are defined in app.workflows.investigation_graph and
re-exported here for clean imports and testability.

Usage:
    from app.agents import analyze_incident, create_plan

    # In tests — call nodes directly without the full graph:
    updates = await analyze_incident(state)
"""

from app.workflows.investigation_graph import (
    analyze_incident,
    create_plan,
    collect_evidence,
    generate_hypotheses,
    test_hypotheses,
    validate_evidence,
    rank_root_causes,
    generate_remediation,
    safety_check,
    awaiting_approval,
    generate_report,
)

__all__ = [
    "analyze_incident",
    "create_plan",
    "collect_evidence",
    "generate_hypotheses",
    "test_hypotheses",
    "validate_evidence",
    "rank_root_causes",
    "generate_remediation",
    "safety_check",
    "awaiting_approval",
    "generate_report",
]
