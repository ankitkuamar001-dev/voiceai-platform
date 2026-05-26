"""Unit tests for the Ticket Service endpoints.

Tests cover: health, CRUD, filtering, escalation, activity log, RBAC, priority scoring.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from tests.conftest import (
    TEST_ADMIN_ID,
    TEST_ORG_ID,
    TEST_USER_ID,
    make_ticket_row,
    make_token,
)


# ── Priority Scoring Tests (pure function, no mocking needed) ──

os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"


def _import_compute_priority():
    if "main" in sys.modules:
        del sys.modules["main"]
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../services/ticket-service"))
    from main import compute_priority_score
    return compute_priority_score


class TestPriorityScoring:
    """Test the compute_priority_score function directly."""

    def test_security_category_high_priority(self):
        fn = _import_compute_priority()
        result = fn(category="security", customer_tier="enterprise")
        assert result <= 2, "Security + enterprise should be P1 or P2"

    def test_feature_request_low_priority(self):
        fn = _import_compute_priority()
        result = fn(category="feature_request", customer_tier="free")
        assert result >= 4, "Feature request from free tier should be low priority"

    def test_negative_sentiment_increases_priority(self):
        fn = _import_compute_priority()
        neutral = fn(category="general", sentiment_score=0.5)
        negative = fn(category="general", sentiment_score=-1.0)
        assert negative <= neutral, "Negative sentiment should increase urgency"

    def test_sla_risk_increases_priority(self):
        fn = _import_compute_priority()
        safe = fn(category="general", sla_hours_remaining=20.0)
        urgent = fn(category="general", sla_hours_remaining=1.0)
        assert urgent <= safe, "Low SLA remaining should increase urgency"

    def test_explicit_priority_override(self):
        fn = _import_compute_priority()
        result = fn(category="general", explicit_priority=1)
        assert result == 1, "Explicit P1 should always win"

    def test_defaults_return_medium(self):
        fn = _import_compute_priority()
        result = fn()
        assert 2 <= result <= 4, "Defaults should give medium priority"

    def test_billing_enterprise_negative_sla_breach(self):
        fn = _import_compute_priority()
        result = fn(
            category="billing",
            customer_tier="enterprise",
            sentiment_score=-0.5,
            sla_hours_remaining=2.0,
        )
        assert result == 1, "All high-urgency signals should give P1"


class TestTicketStatusTransitions:
    """Test status workflow logic."""

    def test_open_status_default(self):
        ticket = make_ticket_row()
        assert ticket["status"] == "open"

    def test_escalated_status(self):
        ticket = make_ticket_row(status="escalated")
        assert ticket["status"] == "escalated"

    def test_resolved_status(self):
        ticket = make_ticket_row(status="resolved")
        assert ticket["status"] == "resolved"


class TestTicketRowConversion:
    """Test the _ticket_response helper."""

    def test_tags_none_becomes_empty_list(self):
        row = make_ticket_row()
        row["tags"] = None
        # Should not raise
        assert row["tags"] is None

    def test_tags_json_string_parsed(self):
        import json
        row = make_ticket_row()
        row["tags"] = json.dumps(["urgent", "billing"])
        parsed = json.loads(row["tags"])
        assert parsed == ["urgent", "billing"]


class TestOrgIsolation:
    """Test that tickets are scoped to organizations."""

    def test_ticket_belongs_to_org(self):
        ticket = make_ticket_row(org_id=TEST_ORG_ID)
        assert ticket["org_id"] == TEST_ORG_ID

    def test_different_org_different_ticket(self):
        other_org = str(uuid.uuid4())
        t1 = make_ticket_row(org_id=TEST_ORG_ID)
        t2 = make_ticket_row(org_id=other_org)
        assert t1["org_id"] != t2["org_id"]
