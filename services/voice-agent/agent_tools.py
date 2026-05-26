"""Agent Tools — callable functions invoked by the LLM via tool-use.

Every tool makes an HTTP call to the appropriate backend micro-service
(ai-brain, ticket-service, etc.) and returns a human-readable result
string that the voice agent relays to the caller.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
import contextvars

logger = logging.getLogger("voice-agent.tools")

conversation_id_ctx = contextvars.ContextVar("conversation_id", default="")
org_id_ctx = contextvars.ContextVar("org_id", default=os.getenv("DEFAULT_ORG_ID", "00000000-0000-0000-0000-000000000000"))

from handoff_manager import request_handoff

AI_BRAIN_URL = os.getenv("AI_BRAIN_URL", "http://localhost:8001")
TICKET_SERVICE_URL = os.getenv("TICKET_SERVICE_URL", "http://localhost:8003")
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8002")
DEFAULT_ORG_ID = os.getenv("DEFAULT_ORG_ID", "00000000-0000-0000-0000-000000000000")

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


# ── Helpers ──


async def _post(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST JSON to a backend service and return the parsed response."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()


async def _get(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """GET from a backend service and return the parsed response."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


# ── Tool implementations ──


async def lookup_order(order_id: str) -> str:
    """Look up order status and details by order ID.

    Calls the ticket-service / orders endpoint.
    """
    try:
        data = await _get(
            f"{TICKET_SERVICE_URL}/api/v1/orders/{order_id}",
        )
        status = data.get("status", "unknown")
        tracking = data.get("tracking_number", "not available")
        eta = data.get("estimated_delivery", "not available")
        return (
            f"Order {order_id}: Status is '{status}'. "
            f"Tracking number: {tracking}. "
            f"Estimated delivery: {eta}."
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return f"I couldn't find an order with ID {order_id}. Could you double-check the order number?"
        logger.error("Order lookup failed: %s", exc)
        return "I'm having trouble looking up that order right now. Let me connect you with someone who can help."
    except Exception as exc:
        logger.error("Order lookup error: %s", exc)
        return "I'm experiencing a temporary issue retrieving order information. Please try again in a moment."


async def create_ticket(subject: str, description: str, priority: str) -> str:
    """Create a support ticket via the ticket-service.

    Maps priority strings to numeric levels expected by the API.
    """
    priority_map = {"low": 4, "medium": 3, "high": 2, "urgent": 1}
    numeric_priority = priority_map.get(priority.lower(), 3)

    try:
        data = await _post(
            f"{TICKET_SERVICE_URL}/api/v1/tickets/",
            {
                "subject": subject,
                "description": description,
                "priority": numeric_priority,
                "org_id": DEFAULT_ORG_ID,
                "customer_id": "00000000-0000-0000-0000-000000000000",
                "source": "voice",
            },
        )
        ticket_number = data.get("ticket_number", "N/A")
        return (
            f"I've created support ticket #{ticket_number} for you. "
            f"Subject: '{subject}'. Priority: {priority}. "
            f"You'll receive updates via email."
        )
    except Exception as exc:
        logger.error("Ticket creation failed: %s", exc)
        return (
            "I wasn't able to create a ticket at the moment. "
            "I've noted your issue, and our team will follow up shortly."
        )


async def check_account(customer_email: str) -> str:
    """Retrieve customer account information by email."""
    try:
        data = await _get(
            f"{AUTH_SERVICE_URL}/api/v1/users/lookup",
            params={"email": customer_email},
        )
        name = data.get("full_name", "Customer")
        status = data.get("status", "unknown")
        user_type = data.get("user_type", "customer")
        return (
            f"Account found for {name} ({customer_email}). "
            f"Account status: {status}. Type: {user_type}."
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return f"I couldn't find an account associated with {customer_email}. Would you like to try a different email?"
        logger.error("Account lookup failed: %s", exc)
        return "I'm having trouble accessing account information right now."
    except Exception as exc:
        logger.error("Account lookup error: %s", exc)
        return "I'm unable to look up the account at this moment. Let me transfer you to someone who can assist."


async def request_human_handoff(reason: str) -> str:
    """Request transfer to a live human agent.

    Creates an escalation record and enqueues the customer.
    """
    try:
        conv_id = conversation_id_ctx.get()
        org_id = org_id_ctx.get()
        
        result = await request_handoff(org_id=org_id, conversation_id=conv_id)
        
        position = result.get("position", 1)
        wait_time = result.get("estimated_wait_sec", 120) // 60
        
        return (
            f"I'm transferring you to a live agent now. "
            f"You are number {position} in the queue. "
            f"The estimated wait time is about {wait_time} minutes. "
            f"Please hold for just a moment."
        )
    except Exception as exc:
        logger.error("Human handoff request failed: %s", exc)
        return (
            "I'm having trouble reaching a live agent right now. "
            "Let me take down your information, and someone will call you back within 15 minutes."
        )


async def process_refund(order_id: str, reason: str) -> str:
    """Process a refund for the given order.

    Calls the ticket-service refund endpoint.
    """
    try:
        data = await _post(
            f"{TICKET_SERVICE_URL}/api/v1/orders/{order_id}/refund",
            {
                "reason": reason,
                "org_id": DEFAULT_ORG_ID,
            },
        )
        refund_id = data.get("refund_id", "N/A")
        amount = data.get("amount", "the full amount")
        return (
            f"Your refund has been initiated. Refund ID: {refund_id}. "
            f"Amount: {amount}. It should appear in your account within 5–10 business days."
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return f"I couldn't find order {order_id}. Could you verify the order number?"
        if exc.response.status_code == 409:
            return f"It looks like a refund for order {order_id} has already been processed."
        logger.error("Refund processing failed: %s", exc)
        return "I'm unable to process the refund right now. I'll escalate this to our billing team."
    except Exception as exc:
        logger.error("Refund error: %s", exc)
        return "There was an issue processing your refund. Let me create a ticket for our billing team to handle."


async def search_knowledge_base(query: str) -> str:
    """Search the knowledge base via the ai-brain RAG endpoint."""
    try:
        data = await _post(
            f"{AI_BRAIN_URL}/api/v1/ai/search-knowledge",
            {
                "query": query,
                "org_id": DEFAULT_ORG_ID,
                "top_k": 3,
            },
        )
        results = data.get("results", [])
        if not results:
            return "I couldn't find any relevant information in our knowledge base for that question."

        # Combine top results into a concise answer
        snippets = []
        for r in results[:3]:
            content = r.get("content", "")
            score = r.get("score", 0)
            if content:
                snippets.append(content.strip())

        combined = " ".join(snippets)
        return f"Based on our knowledge base: {combined}"
    except Exception as exc:
        logger.error("Knowledge base search failed: %s", exc)
        return "I'm unable to search our knowledge base right now. Let me try to help you directly."


async def book_appointment(date: str, time: str, reason: str) -> str:
    """Book an appointment or callback for the customer.

    Posts to the ticket-service appointments endpoint.
    """
    try:
        data = await _post(
            f"{TICKET_SERVICE_URL}/api/v1/appointments/",
            {
                "date": date,
                "time": time,
                "reason": reason,
                "org_id": DEFAULT_ORG_ID,
                "customer_id": "00000000-0000-0000-0000-000000000000",
            },
        )
        appointment_id = data.get("appointment_id", "N/A")
        confirmed_date = data.get("confirmed_date", date)
        confirmed_time = data.get("confirmed_time", time)
        return (
            f"Your appointment has been booked. "
            f"Appointment ID: {appointment_id}. "
            f"Date: {confirmed_date}, Time: {confirmed_time}. "
            f"You'll receive a confirmation via email."
        )
    except Exception as exc:
        logger.error("Appointment booking failed: %s", exc)
        return (
            "I wasn't able to book the appointment right now. "
            "I'll create a callback request, and our team will reach out to schedule."
        )
