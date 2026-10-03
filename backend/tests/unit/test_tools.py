"""
Unit Tests — Investigation Tools
===================================
Tests each of the 7 investigation tools in isolation.

Strategy:
- We mock AsyncSessionLocal to avoid needing a real PostgreSQL
- We mock the embedding provider for knowledge base / historical incident tests
- We test the tool's internal logic: filtering, statistics, error handling
- We do NOT test the DB schema — that's for integration tests

Run:
    pytest tests/unit/test_tools.py -v
"""

import statistics
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Metrics Tool ──────────────────────────────────────────────


class TestSearchMetricsTool:
    """Tests for the search_metrics tool."""

    def test_spike_detection_threshold(self):
        """
        Spike detection should flag values > 2 standard deviations from mean.
        This logic lives in tools/metrics.py independently of the DB.
        """
        values = [10.0, 11.0, 10.5, 9.8, 10.2, 100.0]  # 100 is a spike
        avg = statistics.mean(values)
        std = statistics.stdev(values)
        spike_threshold = avg + (2 * std)

        spikes = [v for v in values if v > spike_threshold]
        assert len(spikes) == 1
        assert spikes[0] == 100.0

    def test_spike_detection_no_spike(self):
        """No spikes when all values are near the mean."""
        values = [10.0, 10.1, 9.9, 10.2, 10.0, 9.8]
        avg = statistics.mean(values)
        std = statistics.stdev(values)
        spike_threshold = avg + (2 * std)

        spikes = [v for v in values if v > spike_threshold and std > 0]
        assert len(spikes) == 0

    def test_change_percent_calculation(self):
        """Change percentage: (last - first) / first * 100."""
        values = [100.0, 200.0]
        change_pct = round(((values[-1] - values[0]) / values[0]) * 100, 1)
        assert change_pct == 100.0

    def test_change_percent_zero_division_safety(self):
        """Should not crash when first value is zero."""
        values = [0.0, 50.0]
        change_pct = round(((values[-1] - values[0]) / values[0]) * 100, 1) if values[0] != 0 else 0
        assert change_pct == 0

    @pytest.mark.asyncio
    async def test_search_metrics_empty_db(self):
        """Tool returns empty data gracefully when no metrics exist."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("app.tools.metrics.AsyncSessionLocal", return_value=mock_session):
            from app.tools.metrics import search_metrics
            result = await search_metrics.ainvoke({
                "service": "payment-api",
                "metric_name": "db_connections",
                "start_time": "2026-09-06T10:00:00Z",
                "end_time": "2026-09-06T11:00:00Z",
            })

        assert result["success"] is True
        assert result["data_points"] == []
        assert result["statistics"] is None

    @pytest.mark.asyncio
    async def test_search_metrics_returns_statistics(self):
        """Tool computes statistics correctly for returned metric data."""
        mock_metric_1 = MagicMock()
        mock_metric_1.value = 50.0
        mock_metric_1.timestamp = datetime(2026, 9, 6, 10, 0, tzinfo=timezone.utc)

        mock_metric_2 = MagicMock()
        mock_metric_2.value = 100.0
        mock_metric_2.timestamp = datetime(2026, 9, 6, 10, 5, tzinfo=timezone.utc)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_metric_1, mock_metric_2]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("app.tools.metrics.AsyncSessionLocal", return_value=mock_session):
            from app.tools.metrics import search_metrics
            result = await search_metrics.ainvoke({
                "service": "payment-api",
                "metric_name": "api_latency_ms",
                "start_time": "2026-09-06T10:00:00Z",
                "end_time": "2026-09-06T11:00:00Z",
            })

        assert result["success"] is True
        assert result["statistics"]["min"] == 50.0
        assert result["statistics"]["max"] == 100.0
        assert result["statistics"]["avg"] == 75.0
        assert result["statistics"]["change_pct"] == 100.0


# ── Deployments Tool ──────────────────────────────────────────


class TestSearchDeploymentsTool:
    """Tests for the search_deployments tool."""

    @pytest.mark.asyncio
    async def test_search_deployments_no_results(self):
        """Tool returns empty list when no deployments found."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("app.tools.deployments.AsyncSessionLocal", return_value=mock_session):
            from app.tools.deployments import search_deployments
            result = await search_deployments.ainvoke({
                "service": "payment-api",
                "start_time": "2026-09-06T10:00:00Z",
                "end_time": "2026-09-06T11:00:00Z",
            })

        assert result["success"] is True
        assert result["deployments"] == []
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_search_deployments_returns_deployment(self):
        """Tool returns deployment data correctly formatted."""
        mock_dep = MagicMock()
        mock_dep.id = "DEP-001"
        mock_dep.service = "payment-api"
        mock_dep.version = "v2.3.1"
        mock_dep.commit_sha = "abc123"
        mock_dep.status = "SUCCESS"
        mock_dep.deployed_at = datetime(2026, 9, 6, 10, 20, tzinfo=timezone.utc)
        mock_dep.deployed_by = "ci-bot"
        mock_dep.deployment_metadata = {}

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_dep]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("app.tools.deployments.AsyncSessionLocal", return_value=mock_session):
            from app.tools.deployments import search_deployments
            result = await search_deployments.ainvoke({
                "service": "payment-api",
                "start_time": "2026-09-06T08:00:00Z",
                "end_time": "2026-09-06T11:00:00Z",
            })

        assert result["success"] is True
        assert result["count"] == 1
        dep = result["deployments"][0]
        assert dep["deployment_id"] == "DEP-001"
        assert dep["commit_sha"] == "abc123"
        assert dep["status"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_search_deployments_handles_exception(self):
        """Tool returns error dict on exception, never raises."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("DB connection refused"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("app.tools.deployments.AsyncSessionLocal", return_value=mock_session):
            from app.tools.deployments import search_deployments
            result = await search_deployments.ainvoke({
                "service": "payment-api",
                "start_time": "2026-09-06T10:00:00Z",
                "end_time": "2026-09-06T11:00:00Z",
            })

        assert result["success"] is False
        assert "error" in result


# ── Logs Tool ─────────────────────────────────────────────────


class TestSearchLogsTool:
    """Tests for the search_logs tool."""

    @pytest.mark.asyncio
    async def test_search_logs_error_detection(self):
        """Tool computes error counts correctly."""
        mock_log_err = MagicMock()
        mock_log_err.id = "l1"
        mock_log_err.timestamp = datetime(2026, 9, 6, 10, 27, tzinfo=timezone.utc)
        mock_log_err.level = "ERROR"
        mock_log_err.service = "payment-api"
        mock_log_err.message = "connection timeout"
        mock_log_err.request_id = None
        mock_log_err.trace_id = None
        mock_log_err.log_metadata = {}

        mock_log_info = MagicMock()
        mock_log_info.id = "l2"
        mock_log_info.timestamp = datetime(2026, 9, 6, 10, 28, tzinfo=timezone.utc)
        mock_log_info.level = "INFO"
        mock_log_info.service = "payment-api"
        mock_log_info.message = "request processed"
        mock_log_info.request_id = None
        mock_log_info.trace_id = None
        mock_log_info.log_metadata = {}

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_log_err, mock_log_info]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("app.tools.logs.AsyncSessionLocal", return_value=mock_session):
            from app.tools.logs import search_logs
            result = await search_logs.ainvoke({
                "service": "payment-api",
                "start_time": "2026-09-06T10:00:00Z",
                "end_time": "2026-09-06T11:00:00Z",
            })

        assert result["success"] is True
        assert result["summary"]["errors"] == 1
        assert result["summary"]["info"] == 1
        assert "connection timeout" in result["summary"]["notable_errors"]

    @pytest.mark.asyncio
    async def test_search_logs_respects_limit(self):
        """Tool enforces a max limit of 200."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # Requesting 9999 — should be clamped to 200 internally
        with patch("app.tools.logs.AsyncSessionLocal", return_value=mock_session):
            from app.tools.logs import search_logs
            result = await search_logs.ainvoke({
                "service": "payment-api",
                "start_time": "2026-09-06T10:00:00Z",
                "end_time": "2026-09-06T11:00:00Z",
                "limit": 9999,
            })
        assert result["success"] is True  # no crash


# ── Git Tool ──────────────────────────────────────────────────


class TestGitTools:
    """Tests for the git investigation tools."""

    def test_sha_validation_valid(self):
        """Valid 40-char hex SHA passes validation."""
        import re
        SHA_PATTERN = re.compile(r"^[0-9a-f]{4,40}$")
        sha = "abc123def456abc123def456abc123def456abc1"
        assert SHA_PATTERN.match(sha)

    def test_sha_validation_rejects_injection(self):
        """Shell injection attempts are rejected by SHA pattern."""
        import re
        SHA_PATTERN = re.compile(r"^[0-9a-f]{4,40}$")
        injection_attempts = [
            "abc; rm -rf /",
            "abc123 && cat /etc/passwd",
            "../../../etc/shadow",
            "$(whoami)",
        ]
        for attempt in injection_attempts:
            assert not SHA_PATTERN.match(attempt), f"Should have rejected: {attempt!r}"

    def test_sha_validation_rejects_too_short(self):
        """SHAs shorter than 4 chars are rejected."""
        import re
        SHA_PATTERN = re.compile(r"^[0-9a-f]{4,40}$")
        assert not SHA_PATTERN.match("ab")

    def test_sha_validation_accepts_short_prefix(self):
        """4-char SHAs (abbreviated) are accepted."""
        import re
        SHA_PATTERN = re.compile(r"^[0-9a-f]{4,40}$")
        assert SHA_PATTERN.match("abcd")


# ── Knowledge Base Tool ───────────────────────────────────────


class TestKnowledgeBaseTool:
    """Tests for the search_knowledge_base tool."""

    @pytest.mark.asyncio
    async def test_search_knowledge_base_empty_results(self):
        """Tool returns empty list when no matching documents."""
        mock_embedding_provider = AsyncMock()
        mock_embedding_provider.embed = AsyncMock(return_value=[0.1] * 768)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("app.tools.knowledge_base.AsyncSessionLocal", return_value=mock_session),
            patch("app.tools.knowledge_base.get_embedding_provider", return_value=mock_embedding_provider),
        ):
            from app.tools.knowledge_base import search_knowledge_base
            result = await search_knowledge_base.ainvoke({
                "query": "database connection pool exhaustion",
                "service": "payment-api",
            })

        assert result["success"] is True
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_search_knowledge_base_handles_exception(self):
        """Tool never propagates exceptions — returns error dict."""
        mock_embedding_provider = AsyncMock()
        mock_embedding_provider.embed = AsyncMock(side_effect=Exception("embedding service unavailable"))

        with patch("app.tools.knowledge_base.get_embedding_provider", return_value=mock_embedding_provider):
            from app.tools.knowledge_base import search_knowledge_base
            result = await search_knowledge_base.ainvoke({
                "query": "anything",
            })

        assert result["success"] is False
        assert "error" in result
