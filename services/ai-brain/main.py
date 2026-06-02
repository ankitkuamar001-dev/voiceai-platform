"""AI Brain Service — FastAPI application (port 8001).

Central AI orchestration service providing:
  • Chat / response generation
  • Intent classification
  • Sentiment analysis
  • RAG-powered knowledge-base search
  • Conversation CRUD with message logging
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# ── Path setup for shared modules ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import text

from shared.utils.database import (
    async_session_factory,
    engine,
    get_redis,
    close_redis,
)
from shared.schemas.models import (
    ConversationUpdate,
    ConversationStatus,
)

from rag_engine import RAGEngine
from llm_orchestrator import LLMOrchestrator
from sentiment_analyzer import SentimentAnalyzer

logger = logging.getLogger("ai-brain")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

# ── Singletons (initialized during lifespan) ──
rag_engine: RAGEngine | None = None
llm_orchestrator: LLMOrchestrator | None = None
sentiment_analyzer: SentimentAnalyzer | None = None


# ── Lifespan ──


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    global rag_engine, llm_orchestrator, sentiment_analyzer

    logger.info("AI Brain starting up …")
    rag_engine = RAGEngine()
    await rag_engine.initialize()

    llm_orchestrator = LLMOrchestrator()
    sentiment_analyzer = SentimentAnalyzer()

    # Warm-up Redis connection
    await get_redis()
    logger.info("AI Brain ready ✓")

    yield

    logger.info("AI Brain shutting down …")
    await close_redis()
    await engine.dispose()
    logger.info("AI Brain stopped.")


# ── App ──

app = FastAPI(
    title="AI Brain Service",
    description="Central AI orchestration for voice customer-support platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from shared.utils.metrics import setup_metrics

setup_metrics(app)


# ── Request / Response Schemas ──


class ChatRequest(BaseModel):
    messages: list[dict[str, str]] = Field(default_factory=list)
    system_prompt: str | None = None
    conversation_id: str | None = None
    org_id: str | None = None
    event: str | None = None  # lifecycle events from voice-agent


class ChatResponse(BaseModel):
    response: str
    intent: str | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IntentRequest(BaseModel):
    text: str
    org_id: str | None = None


class IntentResponse(BaseModel):
    intent: str
    confidence: float
    sub_intents: list[str] = Field(default_factory=list)


class SentimentRequest(BaseModel):
    text: str
    org_id: str | None = None


class SentimentResponse(BaseModel):
    score: float
    emotion: str
    should_escalate: bool


class KnowledgeSearchRequest(BaseModel):
    query: str
    org_id: str | None = None
    top_k: int = 5


class KnowledgeSearchResponse(BaseModel):
    results: list[dict[str, Any]]
    query: str


class SummarizeRequest(BaseModel):
    messages: list[dict[str, str]]
    org_id: str | None = None


class SummarizeResponse(BaseModel):
    summary: str


class ConversationCreateRequest(BaseModel):
    org_id: str
    customer_id: str | None = None
    channel: str = "voice"
    direction: str = "inbound"
    language: str = "en-US"


class MessageCreateRequest(BaseModel):
    content: str
    content_type: str = "text"
    sender_type: str = "customer"
    conversation_id: str | None = None
    org_id: str | None = None
    sender_id: str | None = None
    sequence_num: int = 0


# ── Health ──


@app.get("/health")
async def health_check():
    """Service health check."""
    return {
        "status": "healthy",
        "service": "ai-brain",
        "version": "1.0.0",
    }


# ── AI Endpoints ──


@app.post("/api/v1/ai/chat", response_model=ChatResponse)
async def ai_chat(req: ChatRequest):
    """Send messages to the AI and receive a response."""
    assert llm_orchestrator is not None

    # Handle lifecycle events from voice-agent
    if req.event:
        logger.info("Received event: %s", req.event)
        return ChatResponse(
            response="event_acknowledged",
            metadata={"event": req.event},
        )

    try:
        result = await llm_orchestrator.generate_response(
            messages=req.messages,
            system_prompt=req.system_prompt,
        )
        return ChatResponse(
            response=result["response"],
            intent=result.get("intent"),
            confidence=result.get("confidence"),
            metadata=result.get("metadata", {}),
        )
    except Exception as exc:
        logger.error("Chat generation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to generate response")


@app.post("/api/v1/ai/classify-intent", response_model=IntentResponse)
async def classify_intent(req: IntentRequest):
    """Classify the intent of user text."""
    assert llm_orchestrator is not None

    try:
        result = await llm_orchestrator.classify_intent(req.text)
        return IntentResponse(
            intent=result["intent"],
            confidence=result["confidence"],
            sub_intents=result.get("sub_intents", []),
        )
    except Exception as exc:
        logger.error("Intent classification failed: %s", exc)
        raise HTTPException(status_code=500, detail="Intent classification failed")


@app.post("/api/v1/ai/analyze-sentiment", response_model=SentimentResponse)
async def analyze_sentiment(req: SentimentRequest):
    """Analyze the sentiment of user text."""
    assert sentiment_analyzer is not None

    try:
        result = await sentiment_analyzer.analyze(req.text)
        return SentimentResponse(**result)
    except Exception as exc:
        logger.error("Sentiment analysis failed: %s", exc)
        raise HTTPException(status_code=500, detail="Sentiment analysis failed")


@app.post("/api/v1/ai/search-knowledge", response_model=KnowledgeSearchResponse)
async def search_knowledge(req: KnowledgeSearchRequest):
    """Search the knowledge base via RAG."""
    assert rag_engine is not None

    try:
        results = await rag_engine.search(
            query=req.query,
            org_id=req.org_id,
            top_k=req.top_k,
        )
        return KnowledgeSearchResponse(results=results, query=req.query)
    except Exception as exc:
        logger.error("Knowledge search failed: %s", exc)
        raise HTTPException(status_code=500, detail="Knowledge search failed")


@app.post("/api/v1/ai/summarize", response_model=SummarizeResponse)
async def summarize(req: SummarizeRequest):
    """Generate a summary of conversation messages."""
    assert llm_orchestrator is not None

    try:
        summary = await llm_orchestrator.summarize(req.messages)
        return SummarizeResponse(summary=summary)
    except Exception as exc:
        logger.error("Summarization failed: %s", exc)
        raise HTTPException(status_code=500, detail="Summarization failed")


# ── Conversation CRUD ──


@app.post("/api/v1/conversations/", status_code=201)
async def create_conversation(req: ConversationCreateRequest):
    """Create a new conversation record."""
    async with async_session_factory() as session:
        try:
            result = await session.execute(
                text("""
                    INSERT INTO conversations (org_id, channel, direction, language, status)
                    VALUES (:org_id, :channel, :direction, :language, :status)
                    RETURNING id, org_id, channel, direction, language, status,
                              created_at, updated_at
                """),
                {
                    "org_id": req.org_id,
                    "channel": req.channel,
                    "direction": req.direction,
                    "language": req.language,
                    "status": ConversationStatus.INITIATED.value,
                },
            )
            await session.commit()
            row = result.mappings().one()
            return dict(row)
        except Exception as exc:
            await session.rollback()
            logger.error("Failed to create conversation: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to create conversation")


@app.get("/api/v1/conversations/")
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    org_id: str | None = Query(None),
    status: str | None = Query(None),
):
    """List conversations with pagination."""
    offset = (page - 1) * page_size

    async with async_session_factory() as session:
        try:
            # Build WHERE clauses dynamically
            conditions = []
            params: dict[str, Any] = {"limit": page_size, "offset": offset}

            if org_id:
                conditions.append("org_id = :org_id")
                params["org_id"] = org_id
            if status:
                conditions.append("status = :status")
                params["status"] = status

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            # Count total
            count_result = await session.execute(
                text(f"SELECT COUNT(*) FROM conversations {where_clause}"),
                params,
            )
            total = count_result.scalar() or 0

            # Fetch page
            result = await session.execute(
                text(f"""
                    SELECT id, org_id, customer_id, channel, direction, status,
                           sentiment_score, ai_confidence, is_ai_handled,
                           summary, tags, language, created_at, updated_at,
                           started_at, ended_at
                    FROM conversations
                    {where_clause}
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                """),
                params,
            )
            rows = [dict(r) for r in result.mappings().all()]

            total_pages = max(1, (total + page_size - 1) // page_size)
            return {
                "items": rows,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
            }
        except Exception as exc:
            logger.error("Failed to list conversations: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to list conversations")


@app.get("/api/v1/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get a conversation with its messages."""
    async with async_session_factory() as session:
        try:
            # Fetch conversation
            conv_result = await session.execute(
                text("""
                    SELECT id, org_id, customer_id, assigned_agent_id,
                           channel, direction, status, sentiment_score,
                           ai_confidence, is_ai_handled, transfer_count,
                           summary, tags, language, livekit_room_id,
                           created_at, updated_at, started_at, ended_at
                    FROM conversations
                    WHERE id = :id
                """),
                {"id": conversation_id},
            )
            conv_row = conv_result.mappings().one_or_none()
            if conv_row is None:
                raise HTTPException(status_code=404, detail="Conversation not found")

            # Fetch messages
            msg_result = await session.execute(
                text("""
                    SELECT id, conversation_id, org_id, sender_id, sender_type,
                           content, content_type, confidence, sentiment,
                           intent, sequence_num, created_at
                    FROM messages
                    WHERE conversation_id = :conversation_id
                    ORDER BY sequence_num ASC
                """),
                {"conversation_id": conversation_id},
            )
            messages = [dict(r) for r in msg_result.mappings().all()]

            conversation = dict(conv_row)
            conversation["messages"] = messages
            return conversation
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Failed to get conversation: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to fetch conversation")


@app.post("/api/v1/conversations/{conversation_id}/messages", status_code=201)
async def add_message(conversation_id: str, req: MessageCreateRequest):
    """Add a message to an existing conversation."""
    async with async_session_factory() as session:
        try:
            org_id = req.org_id or "00000000-0000-0000-0000-000000000000"

            result = await session.execute(
                text("""
                    INSERT INTO messages
                        (conversation_id, org_id, sender_id, sender_type,
                         content, content_type, sequence_num)
                    VALUES
                        (:conversation_id, :org_id, :sender_id, :sender_type,
                         :content, :content_type, :sequence_num)
                    RETURNING id, conversation_id, org_id, sender_id, sender_type,
                              content, content_type, sequence_num, created_at
                """),
                {
                    "conversation_id": conversation_id,
                    "org_id": org_id,
                    "sender_id": req.sender_id,
                    "sender_type": req.sender_type,
                    "content": req.content,
                    "content_type": req.content_type,
                    "sequence_num": req.sequence_num,
                },
            )
            await session.commit()
            row = result.mappings().one()
            return dict(row)
        except Exception as exc:
            await session.rollback()
            logger.error("Failed to add message: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to add message")


@app.patch("/api/v1/conversations/{conversation_id}")
async def update_conversation(conversation_id: str, req: ConversationUpdate):
    """Update a conversation (status, sentiment, summary, etc.)."""
    async with async_session_factory() as session:
        try:
            # Build SET clause from non-None fields
            updates = req.model_dump(exclude_none=True)
            if not updates:
                raise HTTPException(status_code=400, detail="No fields to update")

            set_parts = []
            params: dict[str, Any] = {"id": conversation_id}
            for key, value in updates.items():
                if key == "tags":
                    # Store tags as a JSON array
                    set_parts.append(f"{key} = :val_{key}::jsonb")
                    import json as _json

                    params[f"val_{key}"] = _json.dumps(value)
                else:
                    set_parts.append(f"{key} = :val_{key}")
                    params[f"val_{key}"] = (
                        value if not isinstance(value, list) else str(value)
                    )

            set_parts.append("updated_at = NOW()")
            set_clause = ", ".join(set_parts)

            result = await session.execute(
                text(f"""
                    UPDATE conversations
                    SET {set_clause}
                    WHERE id = :id
                    RETURNING id, org_id, status, sentiment_score, ai_confidence,
                              summary, tags, updated_at
                """),
                params,
            )
            await session.commit()

            row = result.mappings().one_or_none()
            if row is None:
                raise HTTPException(status_code=404, detail="Conversation not found")
            return dict(row)
        except HTTPException:
            raise
        except Exception as exc:
            await session.rollback()
            logger.error("Failed to update conversation: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to update conversation")


# ── Runner ──

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8001")),
        reload=os.getenv("DEBUG", "false").lower() == "true",
        log_level="info",
    )
