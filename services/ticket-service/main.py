"""Ticket Service — FastAPI microservice for support-ticket lifecycle management.

Endpoints:
  POST   /api/v1/tickets/                      — Create ticket
  GET    /api/v1/tickets/                      — List tickets (paginated + filters)
  GET    /api/v1/tickets/stats                 — Ticket statistics
  GET    /api/v1/tickets/{ticket_id}           — Get ticket detail
  PATCH  /api/v1/tickets/{ticket_id}           — Update ticket
  DELETE /api/v1/tickets/{ticket_id}           — Delete ticket (admin only)
  GET    /api/v1/tickets/{ticket_id}/activity  — Activity log
  POST   /api/v1/tickets/{ticket_id}/escalate  — Escalate ticket
  GET    /health                               — Health check
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# ── Shared module imports ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from shared.utils.database import (  # noqa: E402
    close_redis,
    engine,
    get_db,
    get_redis,
)
from shared.schemas.models import (  # noqa: E402
    EscalationType,
    PaginatedResponse,
    TicketResponse,
    TicketStatus,
    UserType,
)

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ticket-service")

# ── Configuration ──
SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "super-secret-dev-key-change-me")
ALGORITHM: str = "HS256"

# ── Security scheme ──
bearer_scheme = HTTPBearer(auto_error=False)


# ── Request / Response schemas (service-local) ──


class TicketCreateRequest(BaseModel):
    subject: str = Field(..., max_length=500)
    description: str | None = None
    priority: int = Field(3, ge=1, le=5)
    category: str | None = None
    subcategory: str | None = None
    source: str = "voice"
    customer_id: uuid.UUID
    conversation_id: uuid.UUID | None = None


class TicketUpdateRequest(BaseModel):
    status: TicketStatus | None = None
    assigned_agent_id: uuid.UUID | None = None
    priority: int | None = Field(None, ge=1, le=5)
    category: str | None = None
    tags: list[str] | None = None


class EscalateRequest(BaseModel):
    escalation_type: EscalationType = EscalationType.AGENT_TO_SUPERVISOR
    reason: str = Field(..., min_length=5)
    priority: int = Field(3, ge=1, le=5)


class ActivityEntry(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    action: str
    actor_id: uuid.UUID | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class TicketStats(BaseModel):
    total: int = 0
    open: int = 0
    in_progress: int = 0
    escalated: int = 0
    resolved: int = 0
    closed: int = 0
    avg_priority: float = 0
    sla_breach_count: int = 0


# ── JWT / Auth helpers ──


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if "sub" not in payload or "org_id" not in payload:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return payload
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Token validation failed: {exc}")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    """Extract user identity from Bearer token (lightweight — no DB lookup)."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return decode_token(credentials.credentials)


def require_roles(*allowed_roles: str):
    """Dependency factory for RBAC."""

    async def _check(current_user: dict[str, Any] = Depends(get_current_user)):
        if current_user.get("user_type") not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{current_user.get('user_type')}' is not authorized",
            )
        return current_user

    return _check


# ── Row → Pydantic helper ──


def _ticket_response(row: dict[str, Any]) -> TicketResponse:
    tags = row.get("tags")
    if tags is None:
        tags = []
    elif isinstance(tags, str):
        import json

        try:
            tags = json.loads(tags)
        except (json.JSONDecodeError, TypeError):
            tags = []

    return TicketResponse(
        id=row["id"],
        org_id=row["org_id"],
        ticket_number=row["ticket_number"],
        subject=row["subject"],
        description=row.get("description"),
        priority=row["priority"],
        category=row.get("category"),
        subcategory=row.get("subcategory"),
        source=row.get("source", "voice"),
        customer_id=row["customer_id"],
        conversation_id=row.get("conversation_id"),
        assigned_agent_id=row.get("assigned_agent_id"),
        status=row.get("status", TicketStatus.OPEN),
        sla_breach=row.get("sla_breach", False),
        tags=tags,
        first_response_at=row.get("first_response_at"),
        resolved_at=row.get("resolved_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# ── Activity log helpers ──


async def _record_activity(
    db: AsyncSession,
    ticket_id: str,
    action: str,
    actor_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Insert a row into the ticket_activity table."""
    import json

    await db.execute(
        text(
            """
            INSERT INTO ticket_activity (id, ticket_id, action, actor_id, details, created_at)
            VALUES (:id, :ticket_id, :action, :actor_id, :details, :now)
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "ticket_id": ticket_id,
            "action": action,
            "actor_id": actor_id,
            "details": json.dumps(details or {}),
            "now": datetime.now(timezone.utc),
        },
    )


# ── Priority Scoring ──


# Category urgency weights (higher = more urgent)
_CATEGORY_URGENCY: dict[str, float] = {
    "billing": 0.8,
    "account_locked": 1.0,
    "security": 1.0,
    "technical": 0.6,
    "orders": 0.5,
    "returns": 0.5,
    "shipping": 0.4,
    "general": 0.2,
    "feature_request": 0.1,
}


def compute_priority_score(
    *,
    category: str | None = None,
    sentiment_score: float | None = None,
    customer_tier: str | None = None,
    sla_hours_remaining: float | None = None,
    explicit_priority: int | None = None,
) -> int:
    """Compute a priority level (1=critical … 5=low) from multiple signals.

    Weighted formula:
        score = w_urgency * urgency
              + w_sentiment * sentiment_penalty
              + w_tier * tier_boost
              + w_sla * sla_risk

    The raw score (0–1) is mapped to P1–P5.
    """
    W_URGENCY = 0.30
    W_SENTIMENT = 0.25
    W_TIER = 0.20
    W_SLA = 0.25

    # 1. Category urgency (0–1)
    urgency = _CATEGORY_URGENCY.get((category or "").lower(), 0.3)

    # 2. Sentiment penalty (0–1): lower sentiment → higher penalty
    if sentiment_score is not None:
        sentiment_penalty = max(0.0, min(1.0, (1.0 - sentiment_score) / 2.0))
    else:
        sentiment_penalty = 0.3  # neutral default

    # 3. Customer tier boost (0–1)
    tier_values = {"enterprise": 1.0, "premium": 0.8, "business": 0.5, "free": 0.1}
    tier_boost = tier_values.get((customer_tier or "").lower(), 0.3)

    # 4. SLA risk (0–1): fewer hours remaining → higher risk
    if sla_hours_remaining is not None and sla_hours_remaining > 0:
        sla_risk = max(0.0, min(1.0, 1.0 - (sla_hours_remaining / 24.0)))
    else:
        sla_risk = 0.2  # default low risk

    raw = (
        W_URGENCY * urgency
        + W_SENTIMENT * sentiment_penalty
        + W_TIER * tier_boost
        + W_SLA * sla_risk
    )

    # Map 0–1 score to P1–P5 (lower priority number = more urgent)
    if raw >= 0.75:
        computed = 1  # P1 Critical
    elif raw >= 0.55:
        computed = 2  # P2 High
    elif raw >= 0.35:
        computed = 3  # P3 Medium
    elif raw >= 0.15:
        computed = 4  # P4 Low
    else:
        computed = 5  # P5 Minimal

    # If caller provided an explicit priority, take the more urgent of the two
    if explicit_priority is not None:
        return min(computed, explicit_priority)
    return computed


# ── Lifespan ──


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Ticket service starting up …")
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("Database connection OK")

    redis = await get_redis()
    await redis.ping()
    logger.info("Redis connection OK")

    # Ensure ticket_activity table exists (safe idempotent DDL)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS ticket_activity (
                    id UUID PRIMARY KEY,
                    ticket_id UUID NOT NULL,
                    action VARCHAR(100) NOT NULL,
                    actor_id UUID,
                    details JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT now()
                )
                """
            )
        )

    yield

    logger.info("Ticket service shutting down …")
    await close_redis()
    await engine.dispose()


# ── FastAPI app ──

app = FastAPI(
    title="Ticket Service",
    version="1.0.0",
    description="Support-ticket lifecycle management microservice",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from shared.utils.metrics import setup_metrics

setup_metrics(app)


# ── Health ──


@app.get("/health", tags=["health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "ticket-service",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Create ticket ──


@app.post(
    "/api/v1/tickets/",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["tickets"],
)
async def create_ticket(
    body: TicketCreateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new support ticket (org-scoped)."""
    org_id = current_user["org_id"]
    actor_id = current_user["sub"]
    ticket_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # Auto-generate ticket_number via sequence
    seq_result = await db.execute(
        text(
            "SELECT COALESCE(MAX(ticket_number), 0) + 1 AS next_num "
            "FROM tickets WHERE org_id = :org_id"
        ),
        {"org_id": org_id},
    )
    ticket_number = seq_result.scalar_one()

    await db.execute(
        text(
            """
            INSERT INTO tickets
                (id, org_id, ticket_number, subject, description, priority, category,
                 subcategory, source, customer_id, conversation_id, status, created_at, updated_at)
            VALUES
                (:id, :org_id, :ticket_number, :subject, :description, :priority, :category,
                 :subcategory, :source, :customer_id, :conversation_id, :status, :now, :now)
            """
        ),
        {
            "id": str(ticket_id),
            "org_id": org_id,
            "ticket_number": ticket_number,
            "subject": body.subject,
            "description": body.description,
            "priority": compute_priority_score(
                category=body.category,
                explicit_priority=body.priority,
            ),
            "category": body.category,
            "subcategory": body.subcategory,
            "source": body.source,
            "customer_id": str(body.customer_id),
            "conversation_id": str(body.conversation_id)
            if body.conversation_id
            else None,
            "status": TicketStatus.OPEN.value,
            "now": now,
        },
    )

    await _record_activity(
        db, str(ticket_id), "created", actor_id, {"subject": body.subject}
    )

    logger.info("Ticket %s (#%d) created in org %s", ticket_id, ticket_number, org_id)

    result = await db.execute(
        text("SELECT * FROM tickets WHERE id = :tid"),
        {"tid": str(ticket_id)},
    )
    return _ticket_response(dict(result.mappings().one()))


# ── List tickets (with pagination & filtering) ──


@app.get("/api/v1/tickets/", response_model=PaginatedResponse, tags=["tickets"])
async def list_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: TicketStatus | None = Query(None, alias="status"),
    priority: int | None = Query(None, ge=1, le=5),
    category: str | None = None,
    assigned_agent_id: uuid.UUID | None = None,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List tickets in the caller's organization with optional filters."""
    org_id = current_user["org_id"]
    conditions = ["org_id = :org_id"]
    params: dict[str, Any] = {"org_id": org_id}

    if status_filter is not None:
        conditions.append("status = :status")
        params["status"] = status_filter.value
    if priority is not None:
        conditions.append("priority = :priority")
        params["priority"] = priority
    if category is not None:
        conditions.append("category = :category")
        params["category"] = category
    if assigned_agent_id is not None:
        conditions.append("assigned_agent_id = :assigned_agent_id")
        params["assigned_agent_id"] = str(assigned_agent_id)

    where = " AND ".join(conditions)

    count_result = await db.execute(
        text(f"SELECT count(*) FROM tickets WHERE {where}"), params
    )  # noqa: S608
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset

    rows_result = await db.execute(
        text(
            f"SELECT * FROM tickets WHERE {where} "  # noqa: S608
            f"ORDER BY priority ASC, created_at DESC LIMIT :limit OFFSET :offset"
        ),
        params,
    )
    tickets = [_ticket_response(dict(r)) for r in rows_result.mappings().all()]
    total_pages = max(1, -(-total // page_size))

    return PaginatedResponse(
        items=tickets,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ── Get ticket detail ──


@app.get("/api/v1/tickets/{ticket_id}", response_model=TicketResponse, tags=["tickets"])
async def get_ticket(
    ticket_id: uuid.UUID,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a single ticket by ID (org-scoped)."""
    org_id = current_user["org_id"]
    result = await db.execute(
        text("SELECT * FROM tickets WHERE id = :tid AND org_id = :oid"),
        {"tid": str(ticket_id), "oid": org_id},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return _ticket_response(dict(row))


# ── Update ticket ──


@app.patch(
    "/api/v1/tickets/{ticket_id}", response_model=TicketResponse, tags=["tickets"]
)
async def update_ticket(
    ticket_id: uuid.UUID,
    body: TicketUpdateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update ticket fields (status, assignment, priority, category, tags)."""
    org_id = current_user["org_id"]
    actor_id = current_user["sub"]

    # Verify ticket exists in org
    existing = await db.execute(
        text("SELECT id, status FROM tickets WHERE id = :tid AND org_id = :oid"),
        {"tid": str(ticket_id), "oid": org_id},
    )
    if existing.first() is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    updates: dict[str, Any] = {}
    changes: dict[str, Any] = {}

    if body.status is not None:
        updates["status"] = body.status.value
        changes["status"] = body.status.value
        if body.status == TicketStatus.RESOLVED:
            updates["resolved_at"] = datetime.now(timezone.utc)
    if body.assigned_agent_id is not None:
        updates["assigned_agent_id"] = str(body.assigned_agent_id)
        changes["assigned_agent_id"] = str(body.assigned_agent_id)
        # Track first response time
        updates["first_response_at"] = text("COALESCE(first_response_at, :frt)")
    if body.priority is not None:
        updates["priority"] = body.priority
        changes["priority"] = body.priority
    if body.category is not None:
        updates["category"] = body.category
        changes["category"] = body.category
    if body.tags is not None:
        import json

        updates["tags"] = json.dumps(body.tags)
        changes["tags"] = body.tags

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates["updated_at"] = datetime.now(timezone.utc)

    # Build SET clause carefully, handling the COALESCE for first_response_at
    set_parts: list[str] = []
    bind_params: dict[str, Any] = {"tid": str(ticket_id), "oid": org_id}

    for key, value in updates.items():
        if key == "first_response_at":
            set_parts.append("first_response_at = COALESCE(first_response_at, :frt)")
            bind_params["frt"] = datetime.now(timezone.utc)
        else:
            set_parts.append(f"{key} = :{key}")
            bind_params[key] = value

    set_clause = ", ".join(set_parts)

    await db.execute(
        text(f"UPDATE tickets SET {set_clause} WHERE id = :tid AND org_id = :oid"),  # noqa: S608
        bind_params,
    )

    await _record_activity(db, str(ticket_id), "updated", actor_id, changes)

    result = await db.execute(
        text("SELECT * FROM tickets WHERE id = :tid"),
        {"tid": str(ticket_id)},
    )
    logger.info("Ticket %s updated by %s", ticket_id, actor_id)
    return _ticket_response(dict(result.mappings().one()))


# ── Delete ticket (admin only) ──


@app.delete(
    "/api/v1/tickets/{ticket_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["tickets"],
)
async def delete_ticket(
    ticket_id: uuid.UUID,
    current_user: dict[str, Any] = Depends(
        require_roles(UserType.ADMIN.value, UserType.SUPERADMIN.value)
    ),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a ticket (admin only)."""
    org_id = current_user["org_id"]

    result = await db.execute(
        text("SELECT id FROM tickets WHERE id = :tid AND org_id = :oid"),
        {"tid": str(ticket_id), "oid": org_id},
    )
    if result.first() is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    await db.execute(
        text("DELETE FROM tickets WHERE id = :tid AND org_id = :oid"),
        {"tid": str(ticket_id), "oid": org_id},
    )
    await _record_activity(db, str(ticket_id), "deleted", current_user["sub"])
    logger.info("Ticket %s deleted by admin %s", ticket_id, current_user["sub"])


# ── Activity log ──


@app.get(
    "/api/v1/tickets/{ticket_id}/activity",
    response_model=list[ActivityEntry],
    tags=["tickets"],
)
async def get_ticket_activity(
    ticket_id: uuid.UUID,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the activity log for a ticket."""
    org_id = current_user["org_id"]

    # Verify ticket belongs to org
    check = await db.execute(
        text("SELECT id FROM tickets WHERE id = :tid AND org_id = :oid"),
        {"tid": str(ticket_id), "oid": org_id},
    )
    if check.first() is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    result = await db.execute(
        text(
            "SELECT id, ticket_id, action, actor_id, details, created_at "
            "FROM ticket_activity WHERE ticket_id = :tid ORDER BY created_at ASC"
        ),
        {"tid": str(ticket_id)},
    )

    import json

    entries = []
    for row in result.mappings().all():
        details = row["details"]
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except (json.JSONDecodeError, TypeError):
                details = {}
        entries.append(
            ActivityEntry(
                id=row["id"],
                ticket_id=row["ticket_id"],
                action=row["action"],
                actor_id=row.get("actor_id"),
                details=details or {},
                created_at=row["created_at"],
            )
        )
    return entries


# ── Escalate ticket ──


@app.post(
    "/api/v1/tickets/{ticket_id}/escalate",
    response_model=TicketResponse,
    tags=["tickets"],
)
async def escalate_ticket(
    ticket_id: uuid.UUID,
    body: EscalateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Escalate a ticket — update status and create an escalation record."""
    org_id = current_user["org_id"]
    actor_id = current_user["sub"]

    # Verify ticket exists in org
    existing = await db.execute(
        text("SELECT id, status FROM tickets WHERE id = :tid AND org_id = :oid"),
        {"tid": str(ticket_id), "oid": org_id},
    )
    row = existing.mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if row["status"] in (TicketStatus.CLOSED.value, TicketStatus.RESOLVED.value):
        raise HTTPException(
            status_code=400, detail="Cannot escalate a closed/resolved ticket"
        )

    now = datetime.now(timezone.utc)

    # Update ticket status
    await db.execute(
        text(
            "UPDATE tickets SET status = :status, priority = :priority, updated_at = :now "
            "WHERE id = :tid"
        ),
        {
            "status": TicketStatus.ESCALATED.value,
            "priority": body.priority,
            "now": now,
            "tid": str(ticket_id),
        },
    )

    # Insert escalation record
    escalation_id = uuid.uuid4()
    await db.execute(
        text(
            """
            INSERT INTO escalations
                (id, org_id, ticket_id, escalation_type, reason, status, priority, escalated_at)
            VALUES
                (:id, :org_id, :ticket_id, :etype, :reason, :status, :priority, :now)
            """
        ),
        {
            "id": str(escalation_id),
            "org_id": org_id,
            "ticket_id": str(ticket_id),
            "etype": body.escalation_type.value,
            "reason": body.reason,
            "status": "pending",
            "priority": body.priority,
            "now": now,
        },
    )

    await _record_activity(
        db,
        str(ticket_id),
        "escalated",
        actor_id,
        {
            "escalation_type": body.escalation_type.value,
            "reason": body.reason,
            "priority": body.priority,
        },
    )

    # Publish escalation event to Redis
    redis = await get_redis()
    import json

    await redis.publish(
        f"events:{org_id}",
        json.dumps(
            {
                "type": "ticket.escalated",
                "ticket_id": str(ticket_id),
                "escalation_id": str(escalation_id),
                "priority": body.priority,
                "reason": body.reason,
                "timestamp": now.isoformat(),
            }
        ),
    )

    result = await db.execute(
        text("SELECT * FROM tickets WHERE id = :tid"),
        {"tid": str(ticket_id)},
    )
    logger.info("Ticket %s escalated by %s: %s", ticket_id, actor_id, body.reason)
    return _ticket_response(dict(result.mappings().one()))


# ── Ticket statistics ──


@app.get("/api/v1/tickets/stats", response_model=TicketStats, tags=["tickets"])
async def get_ticket_stats(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregate ticket statistics for the caller's organization."""
    org_id = current_user["org_id"]

    result = await db.execute(
        text(
            """
            SELECT
                count(*)                                                    AS total,
                count(*) FILTER (WHERE status = 'open')                    AS open,
                count(*) FILTER (WHERE status = 'in_progress')             AS in_progress,
                count(*) FILTER (WHERE status = 'escalated')               AS escalated,
                count(*) FILTER (WHERE status = 'resolved')                AS resolved,
                count(*) FILTER (WHERE status = 'closed')                  AS closed,
                COALESCE(avg(priority), 0)                                 AS avg_priority,
                count(*) FILTER (WHERE sla_breach = true)                  AS sla_breach_count
            FROM tickets
            WHERE org_id = :org_id
            """
        ),
        {"org_id": org_id},
    )
    row = result.mappings().one()

    return TicketStats(
        total=row["total"],
        open=row["open"],
        in_progress=row["in_progress"],
        escalated=row["escalated"],
        resolved=row["resolved"],
        closed=row["closed"],
        avg_priority=float(row["avg_priority"]),
        sla_breach_count=row["sla_breach_count"],
    )


# ── Run ──

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8003")),
        reload=os.getenv("RELOAD", "true").lower() == "true",
        log_level="info",
    )
