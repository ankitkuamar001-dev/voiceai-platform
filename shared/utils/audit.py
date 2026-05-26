"""Audit log helper — records user actions for compliance and security.

Usage:
    await record_audit(
        db, org_id="...", user_id="...",
        action="ticket.created", resource_type="ticket", resource_id="...",
        details={"subject": "..."}, ip_address="1.2.3.4",
    )
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def record_audit(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> str:
    """Insert an audit log entry and return its ID.

    Args:
        db: Async database session.
        org_id: Organization ID (for multi-tenant isolation).
        user_id: ID of the user performing the action.
        action: Action name (e.g., "user.created", "ticket.escalated").
        resource_type: Type of resource affected (e.g., "user", "ticket").
        resource_id: ID of the affected resource.
        details: Optional JSON-serializable dict with extra context.
        ip_address: Client IP address (from request).

    Returns:
        The generated audit log entry ID.
    """
    entry_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    await db.execute(
        text(
            """
            INSERT INTO audit_log
                (id, org_id, user_id, action, resource_type, resource_id,
                 details, ip_address, created_at)
            VALUES
                (:id, :org_id, :user_id, :action, :resource_type, :resource_id,
                 :details, :ip_address, :now)
            """
        ),
        {
            "id": entry_id,
            "org_id": org_id,
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": json.dumps(details or {}),
            "ip_address": ip_address,
            "now": now,
        },
    )

    return entry_id


def get_client_ip(request) -> str:
    """Extract client IP from a FastAPI Request, respecting X-Forwarded-For."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if hasattr(request, "client") and request.client:
        return request.client.host
    return "unknown"
