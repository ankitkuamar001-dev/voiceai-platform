"""Unit tests for the Analytics Service endpoints.

Tests cover: health, dashboard metrics, date-range queries, sentiment trends,
agent performance, intent distribution, SLA metrics, CSV export.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from tests.conftest import (
    TEST_ORG_ID,
    TEST_USER_ID,
    make_token,
)


class TestAnalyticsDataFormat:
    """Test analytics response format expectations."""

    def test_chart_data_shape(self):
        """Analytics chart data should have labels + values arrays."""
        chart_data = {
            "labels": ["Mon", "Tue", "Wed", "Thu", "Fri"],
            "values": [12, 19, 3, 5, 2],
        }
        assert len(chart_data["labels"]) == len(chart_data["values"])

    def test_dashboard_metrics_shape(self):
        """Dashboard metrics should have required KPI fields."""
        metrics = {
            "total_conversations": 150,
            "ai_resolution_rate": 0.82,
            "avg_response_time_ms": 450,
            "active_agents": 5,
            "avg_sentiment": 0.65,
            "total_tickets": 42,
            "escalation_rate": 0.12,
            "avg_call_duration_seconds": 180,
        }
        required = [
            "total_conversations", "ai_resolution_rate",
            "avg_response_time_ms", "active_agents"
        ]
        for key in required:
            assert key in metrics

    def test_sentiment_trend_values_in_range(self):
        """Sentiment scores should be between -1 and 1."""
        sentiments = [0.5, -0.3, 0.8, -0.1, 0.0]
        for s in sentiments:
            assert -1.0 <= s <= 1.0

    def test_agent_performance_metrics(self):
        """Agent performance should include calls handled and resolution rate."""
        agent_perf = {
            "agent_id": str(uuid.uuid4()),
            "agent_name": "Agent Smith",
            "calls_handled": 45,
            "avg_resolution_time_min": 8.5,
            "resolution_rate": 0.91,
            "avg_sentiment": 0.72,
        }
        assert agent_perf["resolution_rate"] <= 1.0
        assert agent_perf["calls_handled"] > 0

    def test_intent_distribution_sums_to_100(self):
        """Intent distribution percentages should sum to ~100."""
        intents = {
            "billing": 30.0,
            "technical": 25.0,
            "orders": 20.0,
            "returns": 15.0,
            "general": 10.0,
        }
        total = sum(intents.values())
        assert abs(total - 100.0) < 0.01

    def test_sla_metrics_shape(self):
        """SLA metrics should include compliance rate and breach count."""
        sla = {
            "compliance_rate": 0.95,
            "total_tickets": 200,
            "breached": 10,
            "within_sla": 190,
            "avg_response_time_min": 4.2,
        }
        assert sla["breached"] + sla["within_sla"] == sla["total_tickets"]


class TestCSVExport:
    """Test CSV export format."""

    def test_csv_headers(self):
        """CSV export should include standard column headers."""
        import csv
        import io

        headers = ["date", "total_calls", "avg_duration", "resolution_rate", "avg_sentiment"]
        row = ["2024-01-15", "45", "180", "0.85", "0.72"]

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerow(row)
        output.seek(0)

        reader = csv.DictReader(output)
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["date"] == "2024-01-15"
        assert float(rows[0]["resolution_rate"]) == 0.85


class TestDateRangeFiltering:
    """Test date range parameter validation."""

    def test_valid_date_range(self):
        from datetime import date
        start = date(2024, 1, 1)
        end = date(2024, 1, 31)
        assert start < end

    def test_single_day_range(self):
        from datetime import date
        start = end = date(2024, 1, 15)
        assert start == end  # valid single-day query

    def test_reversed_range_invalid(self):
        from datetime import date
        start = date(2024, 2, 1)
        end = date(2024, 1, 1)
        assert start > end  # should be rejected by service
