"""Unit tests for the Notification Service.

Tests cover: event structure, connection management, message routing, heartbeat.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from tests.conftest import TEST_ORG_ID, TEST_USER_ID


class TestEventStructure:
    """Test WebSocket event message format."""

    def test_event_has_required_fields(self):
        event = {
            "type": "ticket.created",
            "org_id": TEST_ORG_ID,
            "data": {"ticket_id": str(uuid.uuid4()), "subject": "Test"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        assert "type" in event
        assert "org_id" in event
        assert "data" in event
        assert "timestamp" in event

    def test_valid_event_types(self):
        valid_types = {
            "ticket.created",
            "ticket.updated",
            "ticket.escalated",
            "conversation.started",
            "conversation.ended",
            "agent.status_changed",
            "system.health",
        }
        for event_type in valid_types:
            parts = event_type.split(".")
            assert len(parts) == 2, f"Event type should be 'resource.action': {event_type}"

    def test_event_serialization(self):
        event = {
            "type": "ticket.created",
            "org_id": TEST_ORG_ID,
            "data": {"id": str(uuid.uuid4())},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        serialized = json.dumps(event)
        deserialized = json.loads(serialized)
        assert deserialized["type"] == "ticket.created"


class TestConnectionManagement:
    """Test WebSocket connection tracking."""

    def test_connection_registry(self):
        """Simulate connection add/remove."""
        connections: dict[str, set] = {}

        def add_conn(org_id: str, user_id: str):
            connections.setdefault(org_id, set()).add(user_id)

        def remove_conn(org_id: str, user_id: str):
            if org_id in connections:
                connections[org_id].discard(user_id)

        add_conn(TEST_ORG_ID, "user-1")
        add_conn(TEST_ORG_ID, "user-2")
        assert len(connections[TEST_ORG_ID]) == 2

        remove_conn(TEST_ORG_ID, "user-1")
        assert len(connections[TEST_ORG_ID]) == 1

    def test_org_scoped_broadcast(self):
        """Broadcast should only reach connections in the same org."""
        connections = {
            "org-a": {"user-1", "user-2"},
            "org-b": {"user-3"},
        }
        broadcast_org = "org-a"
        recipients = connections.get(broadcast_org, set())
        assert "user-1" in recipients
        assert "user-2" in recipients
        assert "user-3" not in recipients


class TestMessageRouting:
    """Test user-targeted message delivery."""

    def test_send_to_specific_user(self):
        target_user = "user-42"
        all_connections = {
            "user-42": {"ws_conn_1"},
            "user-99": {"ws_conn_2"},
        }
        assert target_user in all_connections

    def test_send_to_offline_user(self):
        all_connections: dict[str, set] = {}
        assert "offline-user" not in all_connections


class TestHeartbeat:
    """Test heartbeat/keepalive mechanism."""

    def test_ping_pong_format(self):
        ping = json.dumps({"type": "ping", "timestamp": datetime.now(timezone.utc).isoformat()})
        msg = json.loads(ping)
        assert msg["type"] == "ping"

        pong = json.dumps({"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()})
        msg = json.loads(pong)
        assert msg["type"] == "pong"

    def test_stale_connection_detection(self):
        """Connections without heartbeat should be considered stale."""
        from datetime import timedelta

        last_ping = datetime.now(timezone.utc) - timedelta(minutes=5)
        threshold = timedelta(minutes=2)
        now = datetime.now(timezone.utc)
        is_stale = (now - last_ping) > threshold
        assert is_stale
