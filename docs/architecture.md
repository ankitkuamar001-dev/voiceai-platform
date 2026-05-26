# Architecture and ADRs

This document details the high-level architecture of the VoiceAI Platform and the Architecture Decision Records (ADRs) that track major technical choices.

## High-Level Architecture

The VoiceAI Platform is a microservices-based system designed to handle real-time voice and messaging interactions using AI.

### Core Components:
1. **API Gateway:** Routes incoming traffic to the appropriate backend service.
2. **Auth Service:** Manages user authentication, authorization, and API keys.
3. **Voice Agent API:** Handles real-time WebRTC and telephony (Twilio) audio streams.
4. **WhatsApp Service:** Integrates with the WhatsApp Business API for text and audio messaging.
5. **AI Brain:** The core logic engine connecting to LLMs, managing conversation state, and function calling.
6. **Analytics Service:** Aggregates call/message metrics and provides dashboard data.
7. **Ticket Service:** Integrates with CRMs (e.g., Zendesk) to create support tickets from conversations.

### Infrastructure:
- **Compute:** Kubernetes (GKE/EKS)
- **Database:** PostgreSQL (Relational data, User data, Logs)
- **Cache/Broker:** Redis (Session state, rate limiting, pub/sub for tasks)
- **Object Storage:** MinIO/S3 (Call recordings, audio files, document knowledge base)

---

## Architecture Decision Records (ADRs)

### ADR-001: Use Microservices Architecture
**Status:** Accepted
**Context:** We need a scalable way to handle distinct domains (Voice, WhatsApp, Auth, Analytics).
**Decision:** We will use a microservices architecture to allow independent scaling, decoupled deployments, and fault isolation.
**Consequences:** Increased operational complexity, requiring Kubernetes and robust CI/CD.

### ADR-002: Use PostgreSQL and SQLAlchemy
**Status:** Accepted
**Context:** We need a reliable relational database for structured data.
**Decision:** We chose PostgreSQL for its robust JSONB support and ACID compliance, with SQLAlchemy as the ORM (asyncpg for async support).
**Consequences:** Familiar SQL patterns, strong schema migrations using Alembic.

### ADR-003: Use Redis for Real-time State and Caching
**Status:** Accepted
**Context:** Voice streams and chat sessions require very low latency state management.
**Decision:** Use Redis to store active session contexts, rate limits, and for pub/sub messaging between services.
**Consequences:** Requires high-availability Redis setup.

### ADR-004: Implement MinIO for S3-Compatible Object Storage
**Status:** Accepted
**Context:** We need to store large binary files (audio recordings, uploaded knowledge base documents) securely and scalably.
**Decision:** Use MinIO as an S3-compatible object storage solution.
**Consequences:** Allows local development parity with production S3 environments, avoiding vendor lock-in.

### ADR-005: Use Kustomize for Kubernetes Deployments
**Status:** Accepted
**Context:** Managing multiple environments (staging, production) requires templating or overlays.
**Decision:** Use Kustomize instead of Helm for our first-party services to keep manifest changes declarative and simple. Helm will still be used for third-party infrastructure (like Prom/Grafana).
**Consequences:** Native integration with `kubectl`, easier reasoning about raw YAML overlays.
