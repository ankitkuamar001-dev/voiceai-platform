"""Shared Pydantic models for the AI Voice Customer Support platform."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ── Enums ──


class UserType(str, enum.Enum):
    CUSTOMER = "customer"
    AGENT = "agent"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending_verification"


class ConversationStatus(str, enum.Enum):
    INITIATED = "initiated"
    RINGING = "ringing"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    TRANSFERRING = "transferring"
    WRAP_UP = "wrap_up"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    FAILED = "failed"


class ConversationChannel(str, enum.Enum):
    VOICE = "voice"
    CHAT = "chat"
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"


class TicketStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_CUSTOMER = "waiting_on_customer"
    WAITING_AGENT = "waiting_on_agent"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class EscalationType(str, enum.Enum):
    AI_TO_AGENT = "ai_to_agent"
    AGENT_TO_SUPERVISOR = "agent_to_supervisor"
    AGENT_TO_SPECIALIST = "agent_to_specialist"
    SLA_BREACH = "sla_breach"
    CUSTOMER_REQUEST = "customer_request"
    SENTIMENT_THRESHOLD = "sentiment_threshold"


class SenderType(str, enum.Enum):
    CUSTOMER = "customer"
    AGENT = "agent"
    AI_BOT = "ai_bot"
    SYSTEM = "system"


class EventCategory(str, enum.Enum):
    CALL = "call"
    AI = "ai"
    AGENT = "agent"
    TICKET = "ticket"
    KB = "kb"
    SYSTEM = "system"
    USER = "user"


# ── Base Models ──


class TimestampMixin(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Organization ──


class OrganizationBase(BaseModel):
    name: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=100)
    domain: str | None = None
    plan: str = "free"
    settings: dict[str, Any] = Field(default_factory=dict)
    max_agents: int = 5
    max_concurrent_calls: int = 10


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationResponse(OrganizationBase, TimestampMixin):
    id: UUID
    is_active: bool = True

    model_config = {"from_attributes": True}


# ── User ──


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., max_length=255)
    phone: str | None = None
    user_type: UserType = UserType.CUSTOMER
    timezone: str = "UTC"
    locale: str = "en-US"


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    org_id: UUID


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase, TimestampMixin):
    id: UUID
    org_id: UUID
    status: UserStatus = UserStatus.ACTIVE
    avatar_url: str | None = None
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Auth ──


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    sub: str  # user_id
    org_id: str
    user_type: str
    exp: int
    iat: int


# ── Conversation ──


class ConversationBase(BaseModel):
    channel: ConversationChannel = ConversationChannel.VOICE
    direction: str = "inbound"
    priority: int = Field(3, ge=1, le=5)
    caller_number: str | None = None
    dialed_number: str | None = None
    language: str = "en-US"


class ConversationCreate(ConversationBase):
    org_id: UUID
    customer_id: UUID | None = None


class ConversationUpdate(BaseModel):
    status: ConversationStatus | None = None
    assigned_agent_id: UUID | None = None
    sentiment_score: float | None = None
    ai_confidence: float | None = None
    summary: str | None = None
    disposition: str | None = None
    tags: list[str] | None = None


class ConversationResponse(ConversationBase, TimestampMixin):
    id: UUID
    org_id: UUID
    customer_id: UUID | None = None
    assigned_agent_id: UUID | None = None
    status: ConversationStatus = ConversationStatus.INITIATED
    sentiment_score: float | None = None
    ai_confidence: float | None = None
    is_ai_handled: bool = True
    transfer_count: int = 0
    queue_wait_seconds: int | None = None
    talk_duration_seconds: int | None = None
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)
    livekit_room_id: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Message ──


class MessageBase(BaseModel):
    content: str
    content_type: str = "text"
    sender_type: SenderType
    language: str | None = None


class MessageCreate(MessageBase):
    conversation_id: UUID
    org_id: UUID
    sender_id: UUID | None = None
    confidence: float | None = None
    sentiment: str | None = None
    intent: str | None = None
    entities: dict[str, Any] = Field(default_factory=dict)
    sequence_num: int


class MessageResponse(MessageBase, BaseModel):
    id: UUID
    conversation_id: UUID
    org_id: UUID
    sender_id: UUID | None = None
    confidence: float | None = None
    sentiment: str | None = None
    intent: str | None = None
    sequence_num: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Ticket ──


class TicketBase(BaseModel):
    subject: str = Field(..., max_length=500)
    description: str | None = None
    priority: int = Field(3, ge=1, le=5)
    category: str | None = None
    subcategory: str | None = None
    source: str = "voice"


class TicketCreate(TicketBase):
    org_id: UUID
    customer_id: UUID
    conversation_id: UUID | None = None


class TicketUpdate(BaseModel):
    status: TicketStatus | None = None
    assigned_agent_id: UUID | None = None
    priority: int | None = None
    category: str | None = None
    tags: list[str] | None = None


class TicketResponse(TicketBase, TimestampMixin):
    id: UUID
    org_id: UUID
    ticket_number: int
    conversation_id: UUID | None = None
    customer_id: UUID
    assigned_agent_id: UUID | None = None
    status: TicketStatus = TicketStatus.OPEN
    sla_breach: bool = False
    tags: list[str] = Field(default_factory=list)
    first_response_at: datetime | None = None
    resolved_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Escalation ──


class EscalationCreate(BaseModel):
    org_id: UUID
    conversation_id: UUID | None = None
    ticket_id: UUID | None = None
    escalation_type: EscalationType
    reason: str
    priority: int = 3
    ai_confidence_at_escalation: float | None = None
    sentiment_at_escalation: float | None = None


class EscalationResponse(BaseModel):
    id: UUID
    org_id: UUID
    conversation_id: UUID | None
    ticket_id: UUID | None
    escalation_type: EscalationType
    reason: str
    status: str
    priority: int
    escalated_at: datetime
    accepted_at: datetime | None
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


# ── Knowledge Base ──


class KBArticleCreate(BaseModel):
    org_id: UUID
    title: str = Field(..., max_length=500)
    content: str
    category_id: UUID | None = None
    author_id: UUID
    excerpt: str | None = None
    visibility: str = "public"
    language: str = "en"
    tags: list[str] = Field(default_factory=list)


class KBArticleResponse(BaseModel):
    id: UUID
    org_id: UUID
    title: str
    slug: str
    content: str
    status: str
    visibility: str
    language: str
    tags: list[str]
    view_count: int
    helpful_count: int
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Analytics ──


class AnalyticsEvent(BaseModel):
    org_id: UUID
    event_type: str
    event_category: EventCategory
    actor_type: str | None = None
    actor_id: UUID | None = None
    conversation_id: UUID | None = None
    ticket_id: UUID | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    numeric_value: float | None = None


class DashboardMetrics(BaseModel):
    active_calls: int = 0
    queued_calls: int = 0
    available_agents: int = 0
    total_calls_today: int = 0
    avg_handle_time_seconds: float = 0
    ai_containment_rate: float = 0
    avg_sentiment: float = 0
    avg_csat: float = 0
    sla_compliance_pct: float = 0
    calls_by_hour: list[dict[str, Any]] = Field(default_factory=list)
    sentiment_distribution: dict[str, int] = Field(default_factory=dict)
    top_intents: list[dict[str, Any]] = Field(default_factory=list)


# ── WebSocket Events ──


class WSEvent(BaseModel):
    type: str
    data: dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    org_id: UUID | None = None


# ── Pagination ──


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
