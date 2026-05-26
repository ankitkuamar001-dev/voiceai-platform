# VoiceAI Platform — API Reference

> Base URL: `http://localhost:8080` (via API Gateway)
> Authentication: Bearer JWT token in `Authorization` header, or `X-API-Key` header.

---

## Auth Service

### POST `/api/v1/auth/register`
Create a new user account.

**Request Body:**
```json
{
  "email": "user@example.com",
  "full_name": "Jane Doe",
  "password": "securePass123",
  "org_id": "uuid",
  "phone": "+1-555-0100",
  "user_type": "customer",
  "timezone": "UTC",
  "locale": "en-US"
}
```

**Response:** `201 Created` → `UserResponse`

---

### POST `/api/v1/auth/login`
Authenticate and receive JWT tokens.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securePass123"
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "expires_in": 1800
}
```

---

### POST `/api/v1/auth/refresh`
Rotate a refresh token.

**Request Body:**
```json
{ "refresh_token": "eyJ..." }
```

**Response:** `200 OK` → `TokenResponse`

---

### GET `/api/v1/auth/me`
Get current user profile. **Requires auth.**

**Response:** `200 OK` → `UserResponse`

---

### PUT `/api/v1/auth/me`
Update current user profile. **Requires auth.**

**Request Body:**
```json
{
  "full_name": "Updated Name",
  "phone": "+1-555-0200",
  "timezone": "America/New_York"
}
```

---

### GET `/api/v1/auth/users`
List users in org. **Admin only.**

**Query Params:** `page`, `page_size`, `status`, `user_type`

---

## Ticket Service

### POST `/api/v1/tickets/`
Create a support ticket. **Requires auth.**

**Request Body:**
```json
{
  "subject": "Billing issue",
  "description": "I was charged twice",
  "priority": 2,
  "category": "billing",
  "customer_id": "uuid",
  "conversation_id": "uuid"
}
```

**Response:** `201 Created` → `TicketResponse`

---

### GET `/api/v1/tickets/`
List tickets with filters. **Requires auth.**

**Query Params:** `page`, `page_size`, `status`, `priority`, `category`, `assigned_agent_id`

---

### GET `/api/v1/tickets/{ticket_id}`
Get ticket detail. **Requires auth.**

---

### PATCH `/api/v1/tickets/{ticket_id}`
Update ticket fields. **Requires auth.**

**Request Body:**
```json
{
  "status": "in_progress",
  "assigned_agent_id": "uuid",
  "priority": 1,
  "tags": ["urgent", "billing"]
}
```

---

### DELETE `/api/v1/tickets/{ticket_id}`
Delete a ticket. **Admin only.**

---

### POST `/api/v1/tickets/{ticket_id}/escalate`
Escalate a ticket.

**Request Body:**
```json
{
  "escalation_type": "agent_to_supervisor",
  "reason": "Customer very frustrated, requesting manager",
  "priority": 1
}
```

---

### GET `/api/v1/tickets/{ticket_id}/activity`
Get ticket activity log.

---

### GET `/api/v1/tickets/stats`
Get aggregate ticket statistics.

**Response:**
```json
{
  "total": 150,
  "open": 42,
  "in_progress": 30,
  "escalated": 8,
  "resolved": 50,
  "closed": 20,
  "avg_priority": 2.8,
  "sla_breach_count": 5
}
```

---

## AI Brain Service

### POST `/api/v1/ai/chat`
Generate an AI response.

**Request Body:**
```json
{
  "message": "What is your return policy?",
  "conversation_id": "uuid",
  "org_id": "uuid"
}
```

**Response:**
```json
{
  "response": "Our return policy allows...",
  "intent": "returns",
  "sentiment": 0.65,
  "confidence": 0.92,
  "sources": ["kb_article_123"]
}
```

---

### POST `/api/v1/ai/classify-intent`
Classify the intent of a message.

**Request Body:**
```json
{ "message": "I need to track my order" }
```

**Response:**
```json
{
  "intent": "orders",
  "confidence": 0.94,
  "sub_intents": ["order_tracking"]
}
```

---

### POST `/api/v1/ai/analyze-sentiment`
Analyze sentiment of text.

**Request Body:**
```json
{ "message": "This is terrible service!" }
```

**Response:**
```json
{
  "sentiment": -0.85,
  "emotion": "frustrated",
  "escalation_recommended": true
}
```

---

### POST `/api/v1/ai/search-knowledge`
Search the knowledge base via RAG.

**Request Body:**
```json
{
  "query": "return policy for electronics",
  "top_k": 5,
  "org_id": "uuid"
}
```

---

## Analytics Service

### GET `/api/v1/analytics/dashboard`
Real-time dashboard metrics. **Requires auth.**

### GET `/api/v1/analytics/conversations`
Conversation analytics. **Query:** `start_date`, `end_date`, `period`

### GET `/api/v1/analytics/sentiment`
Sentiment trends. **Query:** `period` (7d, 30d, 90d)

### GET `/api/v1/analytics/agents`
Agent performance metrics.

### GET `/api/v1/analytics/intents`
Intent distribution.

### GET `/api/v1/analytics/sla`
SLA compliance metrics.

### GET `/api/v1/analytics/export`
CSV export. **Query:** `start_date`, `end_date`, `format=csv`

### POST `/api/v1/analytics/events`
Record an analytics event.

---

## Notification Service

### WS `/ws/{org_id}`
WebSocket connection for real-time events.

**Auth:** Token sent as first message after connect.

**Event Format:**
```json
{
  "type": "ticket.escalated",
  "data": {
    "ticket_id": "uuid",
    "priority": 1
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### POST `/api/v1/notifications/broadcast`
Broadcast event to all connections in an org.

### POST `/api/v1/notifications/send`
Send event to a specific user.

### GET `/api/v1/notifications/connections`
List active WebSocket connections.

---

## Common Response Models

### UserResponse
```json
{
  "id": "uuid",
  "org_id": "uuid",
  "email": "user@example.com",
  "full_name": "Jane Doe",
  "phone": "+1-555-0100",
  "user_type": "customer",
  "status": "active",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

### PaginatedResponse
```json
{
  "items": [],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "total_pages": 5
}
```

### Health Check
All services expose `GET /health`:
```json
{
  "status": "healthy",
  "service": "auth-service",
  "timestamp": "2024-01-15T10:30:00Z"
}
```
