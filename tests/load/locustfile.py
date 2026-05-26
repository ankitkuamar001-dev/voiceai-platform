"""Locust load test for the VoiceAI API platform.

Simulates concurrent users hitting the API gateway:
  - 10% auth (login)
  - 40% ticket CRUD
  - 30% analytics dashboard
  - 20% AI chat

Usage:
  locust -f locustfile.py --host=http://localhost:8080
  locust -f locustfile.py --host=http://localhost:8080 --headless -u 50 -r 5 -t 60s
"""

from __future__ import annotations

import json
import random
import uuid

from locust import HttpUser, between, task


class VoiceAIUser(HttpUser):
    """Simulates a typical API consumer of the VoiceAI platform."""

    wait_time = between(0.5, 2.0)

    # Shared state
    access_token: str | None = None
    org_id: str = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    user_id: str = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    def on_start(self):
        """Login on user spawn to get a valid token."""
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"email": "load-test@voiceai.demo", "password": "loadtest123"},
            name="/auth/login",
        )
        if resp.status_code == 200:
            data = resp.json()
            self.access_token = data.get("access_token")
        else:
            # Fallback: use without auth (will get 401s, tracked as errors)
            self.access_token = None

    @property
    def _headers(self) -> dict[str, str]:
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        return {}

    # ── Auth tasks (10%) ──

    @task(1)
    def login(self):
        self.client.post(
            "/api/v1/auth/login",
            json={"email": "load-test@voiceai.demo", "password": "loadtest123"},
            name="/auth/login",
        )

    # ── Ticket tasks (40%) ──

    @task(2)
    def list_tickets(self):
        self.client.get(
            "/api/v1/tickets/",
            headers=self._headers,
            name="/tickets/list",
        )

    @task(1)
    def create_ticket(self):
        self.client.post(
            "/api/v1/tickets/",
            headers=self._headers,
            json={
                "subject": f"Load test ticket {uuid.uuid4().hex[:8]}",
                "description": "Created by Locust load test",
                "priority": random.randint(1, 5),
                "category": random.choice(["billing", "technical", "orders", "general"]),
                "customer_id": self.user_id,
            },
            name="/tickets/create",
        )

    @task(1)
    def get_ticket_stats(self):
        self.client.get(
            "/api/v1/tickets/stats",
            headers=self._headers,
            name="/tickets/stats",
        )

    # ── Analytics tasks (30%) ──

    @task(2)
    def dashboard_metrics(self):
        self.client.get(
            "/api/v1/analytics/dashboard",
            headers=self._headers,
            name="/analytics/dashboard",
        )

    @task(1)
    def sentiment_trends(self):
        self.client.get(
            "/api/v1/analytics/sentiment?period=7d",
            headers=self._headers,
            name="/analytics/sentiment",
        )

    # ── AI tasks (20%) ──

    @task(2)
    def ai_chat(self):
        messages = [
            "What is your return policy?",
            "I need to track my order",
            "How do I reset my password?",
            "I was charged twice for my subscription",
            "When will my package arrive?",
        ]
        self.client.post(
            "/api/v1/ai/chat",
            headers=self._headers,
            json={
                "message": random.choice(messages),
                "conversation_id": str(uuid.uuid4()),
                "org_id": self.org_id,
            },
            name="/ai/chat",
        )

    # ── WhatsApp tasks (10%) ──

    @task(1)
    def send_whatsapp(self):
        self.client.post(
            "/api/v1/whatsapp/messages/send",
            headers=self._headers,
            json={
                "to": f"+1{random.randint(2000000000, 9999999999)}",
                "body": "This is a load test message from Locust",
            },
            name="/whatsapp/messages/send",
        )

    # ── Recording tasks (10%) ──

    @task(1)
    def get_recording(self):
        rec_id = uuid.uuid4().hex
        self.client.get(
            f"/api/v1/voice/recordings/{rec_id}",
            headers=self._headers,
            name="/voice/recordings/{recording_id}",
        )

    # ── Health check ──

    @task(1)
    def health_check(self):
        self.client.get("/health", name="/health")

