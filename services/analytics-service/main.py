"""Analytics Service — Real-time and historical analytics for the AI Voice platform.

Provides dashboard metrics, conversation analytics, sentiment trends, agent
performance, intent distribution, SLA compliance tracking, event recording,
and CSV data export.  All heavy queries hit PostgreSQL via raw SQL
(``sqlalchemy.text``), with Redis caching (30 s TTL) for hot-path reads.

Run:
    uvicorn main:app --host 0.0.0.0 --port 8004 --reload
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import text

# ── Path bootstrap so shared packages resolve in dev & Docker ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, "/app")

from shared.schemas.models import AnalyticsEvent, DashboardMetrics, EventCategory
from shared.utils.database import (
    RedisKeys,
    async_session_factory,
    close_redis,
    engine,
    get_db,
    get_redis,
)

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("analytics-service")

# ── Constants ──
REDIS_CACHE_TTL = 30  # seconds
DEFAULT_PAGE_SIZE = 50


# ── Pydantic helpers ──


class ChartData(BaseModel):
    """Recharts-ready payload: parallel labels + values arrays."""

    labels: list[str] = Field(default_factory=list)
    values: list[float | int] = Field(default_factory=list)


class TimeSeriesPoint(BaseModel):
    timestamp: str
    value: float


class ConversationAnalytics(BaseModel):
    total: int = 0
    completed: int = 0
    abandoned: int = 0
    ai_handled: int = 0
    avg_duration_seconds: float = 0
    by_channel: ChartData = Field(default_factory=ChartData)
    by_status: ChartData = Field(default_factory=ChartData)
    by_day: ChartData = Field(default_factory=ChartData)


class SentimentTrend(BaseModel):
    by_day: ChartData = Field(default_factory=ChartData)
    distribution: ChartData = Field(default_factory=ChartData)
    avg_sentiment: float = 0


class AgentMetrics(BaseModel):
    agent_id: str
    agent_name: str
    calls_handled: int = 0
    avg_handle_time_seconds: float = 0
    avg_csat: float = 0
    avg_sentiment: float = 0


class AgentPerformanceResponse(BaseModel):
    agents: list[AgentMetrics] = Field(default_factory=list)
    total_agents: int = 0


class IntentDistribution(BaseModel):
    intents: ChartData = Field(default_factory=ChartData)
    total_messages: int = 0


class SLAMetrics(BaseModel):
    total_tickets: int = 0
    breached: int = 0
    compliance_pct: float = 0
    avg_first_response_minutes: float = 0
    avg_resolution_minutes: float = 0
    by_priority: ChartData = Field(default_factory=ChartData)


class EventResponse(BaseModel):
    id: str
    status: str = "recorded"


class HealthResponse(BaseModel):
    status: str = "healthy"
    service: str = "analytics-service"
    timestamp: str


# ── Lifespan ──


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks — warm up DB pool & Redis."""
    logger.info("Starting analytics-service …")
    redis = await get_redis()
    try:
        await redis.ping()
        logger.info("Redis connected ✓")
    except Exception as exc:
        logger.warning("Redis unavailable — caching disabled: %s", exc)

    # Quick DB connectivity check
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        logger.info("PostgreSQL connected ✓")
    except Exception as exc:
        logger.warning("PostgreSQL unavailable: %s", exc)

    yield

    logger.info("Shutting down analytics-service …")
    await close_redis()
    await engine.dispose()


# ── App ──

app = FastAPI(
    title="Analytics Service",
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


# ── Helpers ──


def _default_start() -> date:
    return date.today() - timedelta(days=30)


def _default_end() -> date:
    return date.today()


async def _cached_or_query(
    cache_key: str,
    query_fn,
    ttl: int = REDIS_CACHE_TTL,
) -> Any:
    """Return cached JSON if available, otherwise execute *query_fn* and cache."""
    try:
        redis = await get_redis()
        cached = await redis.get(cache_key)
        if cached:
            logger.debug("Cache HIT: %s", cache_key)
            return json.loads(cached)
    except Exception:
        pass  # Redis down — fall through to DB

    result = await query_fn()

    try:
        redis = await get_redis()
        await redis.set(cache_key, json.dumps(result, default=str), ex=ttl)
    except Exception:
        pass

    return result


def _bucket_sentiment(score: float | None) -> str:
    """Map a –1…1 sentiment score into a human-readable bucket."""
    if score is None:
        return "unknown"
    if score >= 0.3:
        return "positive"
    if score <= -0.3:
        return "negative"
    return "neutral"


# ── Routes ──


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    return HealthResponse(
        status="healthy",
        service="analytics-service",
        timestamp=datetime.utcnow().isoformat(),
    )


# ── 1. Dashboard ──


@app.get("/api/v1/analytics/dashboard", response_model=DashboardMetrics, tags=["analytics"])
async def get_dashboard(
    org_id: str = Query(..., description="Organisation UUID"),
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
):
    """Real-time dashboard metrics — backed by Redis counters + DB fallback."""
    start = start_date or _default_start()
    end = end_date or _default_end()
    cache_key = f"analytics:dashboard:{org_id}:{start}:{end}"

    async def _query():
        async with async_session_factory() as session:
            # Active / queued calls (live state)
            active_q = await session.execute(
                text(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE status = 'in_progress') AS active,
                        COUNT(*) FILTER (WHERE status = 'queued')       AS queued
                    FROM conversations
                    WHERE org_id = :org AND status IN ('in_progress', 'queued')
                    """
                ),
                {"org": org_id},
            )
            row = active_q.mappings().first()
            active_calls = row["active"] if row else 0
            queued_calls = row["queued"] if row else 0

            # Available agents (from users table — agents whose status is 'active')
            agents_q = await session.execute(
                text(
                    """
                    SELECT COUNT(*) AS cnt FROM users
                    WHERE org_id = :org AND user_type = 'agent' AND status = 'active'
                    """
                ),
                {"org": org_id},
            )
            available_agents = agents_q.scalar() or 0

            # Aggregated day-range stats
            stats_q = await session.execute(
                text(
                    """
                    SELECT
                        COUNT(*)                                              AS total,
                        AVG(talk_duration_seconds)                            AS avg_ht,
                        COUNT(*) FILTER (WHERE is_ai_handled = TRUE)          AS ai_cnt,
                        AVG(sentiment_score)                                  AS avg_sent
                    FROM conversations
                    WHERE org_id = :org
                      AND created_at >= :start AND created_at < :end + INTERVAL '1 day'
                    """
                ),
                {"org": org_id, "start": start, "end": end},
            )
            s = stats_q.mappings().first()
            total_today = s["total"] if s else 0
            avg_ht = float(s["avg_ht"] or 0) if s else 0
            ai_cnt = s["ai_cnt"] if s else 0
            avg_sent = float(s["avg_sent"] or 0) if s else 0
            ai_rate = round((ai_cnt / total_today * 100) if total_today else 0, 1)

            # Calls by hour
            hour_q = await session.execute(
                text(
                    """
                    SELECT EXTRACT(HOUR FROM created_at)::int AS hr, COUNT(*) AS cnt
                    FROM conversations
                    WHERE org_id = :org
                      AND created_at >= :start AND created_at < :end + INTERVAL '1 day'
                    GROUP BY hr ORDER BY hr
                    """
                ),
                {"org": org_id, "start": start, "end": end},
            )
            calls_by_hour = [
                {"hour": r["hr"], "count": r["cnt"]}
                for r in hour_q.mappings().all()
            ]

            # Sentiment distribution
            sent_q = await session.execute(
                text(
                    """
                    SELECT sentiment_score FROM conversations
                    WHERE org_id = :org AND sentiment_score IS NOT NULL
                      AND created_at >= :start AND created_at < :end + INTERVAL '1 day'
                    """
                ),
                {"org": org_id, "start": start, "end": end},
            )
            dist: dict[str, int] = {"positive": 0, "neutral": 0, "negative": 0}
            for r in sent_q.mappings().all():
                bucket = _bucket_sentiment(r["sentiment_score"])
                if bucket in dist:
                    dist[bucket] += 1

            # Top intents
            intent_q = await session.execute(
                text(
                    """
                    SELECT intent, COUNT(*) AS cnt
                    FROM messages
                    WHERE org_id = :org AND intent IS NOT NULL
                      AND created_at >= :start AND created_at < :end + INTERVAL '1 day'
                    GROUP BY intent ORDER BY cnt DESC LIMIT 10
                    """
                ),
                {"org": org_id, "start": start, "end": end},
            )
            top_intents = [
                {"intent": r["intent"], "count": r["cnt"]}
                for r in intent_q.mappings().all()
            ]

            # SLA compliance
            sla_q = await session.execute(
                text(
                    """
                    SELECT
                        COUNT(*) AS total,
                        COUNT(*) FILTER (WHERE sla_breach = FALSE) AS ok
                    FROM tickets
                    WHERE org_id = :org
                      AND created_at >= :start AND created_at < :end + INTERVAL '1 day'
                    """
                ),
                {"org": org_id, "start": start, "end": end},
            )
            sla = sla_q.mappings().first()
            sla_total = sla["total"] if sla else 0
            sla_ok = sla["ok"] if sla else 0
            sla_pct = round((sla_ok / sla_total * 100) if sla_total else 100, 1)

            return DashboardMetrics(
                active_calls=active_calls,
                queued_calls=queued_calls,
                available_agents=available_agents,
                total_calls_today=total_today,
                avg_handle_time_seconds=round(avg_ht, 1),
                ai_containment_rate=ai_rate,
                avg_sentiment=round(avg_sent, 2),
                avg_csat=0,  # populated when CSAT survey data available
                sla_compliance_pct=sla_pct,
                calls_by_hour=calls_by_hour,
                sentiment_distribution=dist,
                top_intents=top_intents,
            ).model_dump()

    data = await _cached_or_query(cache_key, _query)
    return DashboardMetrics(**data)


# ── 2. Conversation analytics ──


@app.get("/api/v1/analytics/conversations", response_model=ConversationAnalytics, tags=["analytics"])
async def conversation_analytics(
    org_id: str = Query(...),
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
):
    start = start_date or _default_start()
    end = end_date or _default_end()
    cache_key = f"analytics:conversations:{org_id}:{start}:{end}"

    async def _query():
        async with async_session_factory() as session:
            main = await session.execute(
                text(
                    """
                    SELECT
                        COUNT(*)                                             AS total,
                        COUNT(*) FILTER (WHERE status = 'completed')         AS completed,
                        COUNT(*) FILTER (WHERE status = 'abandoned')         AS abandoned,
                        COUNT(*) FILTER (WHERE is_ai_handled = TRUE)         AS ai_handled,
                        AVG(talk_duration_seconds)                           AS avg_dur
                    FROM conversations
                    WHERE org_id = :org
                      AND created_at >= :start AND created_at < :end + INTERVAL '1 day'
                    """
                ),
                {"org": org_id, "start": start, "end": end},
            )
            m = main.mappings().first()

            # By channel
            ch_q = await session.execute(
                text(
                    """
                    SELECT channel, COUNT(*) AS cnt FROM conversations
                    WHERE org_id = :org
                      AND created_at >= :start AND created_at < :end + INTERVAL '1 day'
                    GROUP BY channel ORDER BY cnt DESC
                    """
                ),
                {"org": org_id, "start": start, "end": end},
            )
            ch_rows = ch_q.mappings().all()

            # By status
            st_q = await session.execute(
                text(
                    """
                    SELECT status, COUNT(*) AS cnt FROM conversations
                    WHERE org_id = :org
                      AND created_at >= :start AND created_at < :end + INTERVAL '1 day'
                    GROUP BY status ORDER BY cnt DESC
                    """
                ),
                {"org": org_id, "start": start, "end": end},
            )
            st_rows = st_q.mappings().all()

            # By day
            day_q = await session.execute(
                text(
                    """
                    SELECT created_at::date AS day, COUNT(*) AS cnt FROM conversations
                    WHERE org_id = :org
                      AND created_at >= :start AND created_at < :end + INTERVAL '1 day'
                    GROUP BY day ORDER BY day
                    """
                ),
                {"org": org_id, "start": start, "end": end},
            )
            day_rows = day_q.mappings().all()

            return ConversationAnalytics(
                total=m["total"],
                completed=m["completed"],
                abandoned=m["abandoned"],
                ai_handled=m["ai_handled"],
                avg_duration_seconds=round(float(m["avg_dur"] or 0), 1),
                by_channel=ChartData(
                    labels=[r["channel"] for r in ch_rows],
                    values=[r["cnt"] for r in ch_rows],
                ),
                by_status=ChartData(
                    labels=[r["status"] for r in st_rows],
                    values=[r["cnt"] for r in st_rows],
                ),
                by_day=ChartData(
                    labels=[str(r["day"]) for r in day_rows],
                    values=[r["cnt"] for r in day_rows],
                ),
            ).model_dump()

    data = await _cached_or_query(cache_key, _query)
    return ConversationAnalytics(**data)


# ── 3. Sentiment ──


@app.get("/api/v1/analytics/sentiment", response_model=SentimentTrend, tags=["analytics"])
async def sentiment_trends(
    org_id: str = Query(...),
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
):
    start = start_date or _default_start()
    end = end_date or _default_end()
    cache_key = f"analytics:sentiment:{org_id}:{start}:{end}"

    async def _query():
        async with async_session_factory() as session:
            # Average sentiment per day
            day_q = await session.execute(
                text(
                    """
                    SELECT created_at::date AS day, AVG(sentiment_score) AS avg_s
                    FROM conversations
                    WHERE org_id = :org AND sentiment_score IS NOT NULL
                      AND created_at >= :start AND created_at < :end + INTERVAL '1 day'
                    GROUP BY day ORDER BY day
                    """
                ),
                {"org": org_id, "start": start, "end": end},
            )
            day_rows = day_q.mappings().all()

            # Distribution
            dist_q = await session.execute(
                text(
                    """
                    SELECT sentiment_score FROM conversations
                    WHERE org_id = :org AND sentiment_score IS NOT NULL
                      AND created_at >= :start AND created_at < :end + INTERVAL '1 day'
                    """
                ),
                {"org": org_id, "start": start, "end": end},
            )
            buckets: dict[str, int] = {"positive": 0, "neutral": 0, "negative": 0}
            all_scores: list[float] = []
            for r in dist_q.mappings().all():
                s = r["sentiment_score"]
                all_scores.append(float(s))
                buckets[_bucket_sentiment(s)] += 1

            avg_sent = round(sum(all_scores) / len(all_scores), 3) if all_scores else 0

            return SentimentTrend(
                by_day=ChartData(
                    labels=[str(r["day"]) for r in day_rows],
                    values=[round(float(r["avg_s"]), 3) for r in day_rows],
                ),
                distribution=ChartData(
                    labels=list(buckets.keys()),
                    values=list(buckets.values()),
                ),
                avg_sentiment=avg_sent,
            ).model_dump()

    data = await _cached_or_query(cache_key, _query)
    return SentimentTrend(**data)


# ── 4. Agent performance ──


@app.get("/api/v1/analytics/agents", response_model=AgentPerformanceResponse, tags=["analytics"])
async def agent_performance(
    org_id: str = Query(...),
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
):
    start = start_date or _default_start()
    end = end_date or _default_end()
    cache_key = f"analytics:agents:{org_id}:{start}:{end}"

    async def _query():
        async with async_session_factory() as session:
            q = await session.execute(
                text(
                    """
                    SELECT
                        u.id::text                       AS agent_id,
                        u.full_name                      AS agent_name,
                        COUNT(c.id)                      AS calls_handled,
                        AVG(c.talk_duration_seconds)     AS avg_ht,
                        AVG(c.sentiment_score)           AS avg_sent
                    FROM users u
                    LEFT JOIN conversations c
                        ON c.assigned_agent_id = u.id
                       AND c.org_id = :org
                       AND c.created_at >= :start
                       AND c.created_at < :end + INTERVAL '1 day'
                    WHERE u.org_id = :org AND u.user_type = 'agent'
                    GROUP BY u.id, u.full_name
                    ORDER BY calls_handled DESC
                    """
                ),
                {"org": org_id, "start": start, "end": end},
            )
            rows = q.mappings().all()
            agents = [
                AgentMetrics(
                    agent_id=r["agent_id"],
                    agent_name=r["agent_name"],
                    calls_handled=r["calls_handled"],
                    avg_handle_time_seconds=round(float(r["avg_ht"] or 0), 1),
                    avg_csat=0,
                    avg_sentiment=round(float(r["avg_sent"] or 0), 3),
                ).model_dump()
                for r in rows
            ]
            return AgentPerformanceResponse(
                agents=[AgentMetrics(**a) for a in agents],
                total_agents=len(agents),
            ).model_dump()

    data = await _cached_or_query(cache_key, _query)
    return AgentPerformanceResponse(**data)


# ── 5. Intents ──


@app.get("/api/v1/analytics/intents", response_model=IntentDistribution, tags=["analytics"])
async def intent_distribution(
    org_id: str = Query(...),
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    limit: int = Query(20, ge=1, le=100),
):
    start = start_date or _default_start()
    end = end_date or _default_end()
    cache_key = f"analytics:intents:{org_id}:{start}:{end}:{limit}"

    async def _query():
        async with async_session_factory() as session:
            q = await session.execute(
                text(
                    """
                    SELECT intent, COUNT(*) AS cnt
                    FROM messages
                    WHERE org_id = :org AND intent IS NOT NULL
                      AND created_at >= :start AND created_at < :end + INTERVAL '1 day'
                    GROUP BY intent ORDER BY cnt DESC
                    LIMIT :lim
                    """
                ),
                {"org": org_id, "start": start, "end": end, "lim": limit},
            )
            rows = q.mappings().all()

            total_q = await session.execute(
                text(
                    """
                    SELECT COUNT(*) AS cnt FROM messages
                    WHERE org_id = :org AND intent IS NOT NULL
                      AND created_at >= :start AND created_at < :end + INTERVAL '1 day'
                    """
                ),
                {"org": org_id, "start": start, "end": end},
            )
            total = total_q.scalar() or 0

            return IntentDistribution(
                intents=ChartData(
                    labels=[r["intent"] for r in rows],
                    values=[r["cnt"] for r in rows],
                ),
                total_messages=total,
            ).model_dump()

    data = await _cached_or_query(cache_key, _query)
    return IntentDistribution(**data)


# ── 6. SLA ──


@app.get("/api/v1/analytics/sla", response_model=SLAMetrics, tags=["analytics"])
async def sla_compliance(
    org_id: str = Query(...),
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
):
    start = start_date or _default_start()
    end = end_date or _default_end()
    cache_key = f"analytics:sla:{org_id}:{start}:{end}"

    async def _query():
        async with async_session_factory() as session:
            main = await session.execute(
                text(
                    """
                    SELECT
                        COUNT(*)                                          AS total,
                        COUNT(*) FILTER (WHERE sla_breach = TRUE)         AS breached,
                        AVG(EXTRACT(EPOCH FROM (first_response_at - created_at)) / 60)
                            FILTER (WHERE first_response_at IS NOT NULL)  AS avg_fr,
                        AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 60)
                            FILTER (WHERE resolved_at IS NOT NULL)        AS avg_res
                    FROM tickets
                    WHERE org_id = :org
                      AND created_at >= :start AND created_at < :end + INTERVAL '1 day'
                    """
                ),
                {"org": org_id, "start": start, "end": end},
            )
            m = main.mappings().first()
            total = m["total"] if m else 0
            breached = m["breached"] if m else 0
            compliance = round(((total - breached) / total * 100) if total else 100, 1)

            # By priority
            pri_q = await session.execute(
                text(
                    """
                    SELECT priority, COUNT(*) AS cnt FROM tickets
                    WHERE org_id = :org AND sla_breach = TRUE
                      AND created_at >= :start AND created_at < :end + INTERVAL '1 day'
                    GROUP BY priority ORDER BY priority
                    """
                ),
                {"org": org_id, "start": start, "end": end},
            )
            pri_rows = pri_q.mappings().all()

            return SLAMetrics(
                total_tickets=total,
                breached=breached,
                compliance_pct=compliance,
                avg_first_response_minutes=round(float(m["avg_fr"] or 0), 1) if m else 0,
                avg_resolution_minutes=round(float(m["avg_res"] or 0), 1) if m else 0,
                by_priority=ChartData(
                    labels=[f"P{r['priority']}" for r in pri_rows],
                    values=[r["cnt"] for r in pri_rows],
                ),
            ).model_dump()

    data = await _cached_or_query(cache_key, _query)
    return SLAMetrics(**data)


# ── 7. Record event ──


@app.post("/api/v1/analytics/events", response_model=EventResponse, tags=["analytics"])
async def record_event(event: AnalyticsEvent):
    """Persist an analytics event and publish to Redis for real-time consumers."""
    event_id = str(uuid.uuid4())
    try:
        async with async_session_factory() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO analytics_events
                        (id, org_id, event_type, event_category, actor_type,
                         actor_id, conversation_id, ticket_id, properties,
                         numeric_value, created_at)
                    VALUES
                        (:id, :org, :etype, :ecat, :atype,
                         :aid, :cid, :tid, :props,
                         :nval, NOW())
                    """
                ),
                {
                    "id": event_id,
                    "org": str(event.org_id),
                    "etype": event.event_type,
                    "ecat": event.event_category.value,
                    "atype": event.actor_type,
                    "aid": str(event.actor_id) if event.actor_id else None,
                    "cid": str(event.conversation_id) if event.conversation_id else None,
                    "tid": str(event.ticket_id) if event.ticket_id else None,
                    "props": json.dumps(event.properties),
                    "nval": event.numeric_value,
                },
            )
            await session.commit()

        # Publish to Redis for real-time notification service
        try:
            redis = await get_redis()
            payload = {
                "id": event_id,
                "type": event.event_type,
                "category": event.event_category.value,
                "org_id": str(event.org_id),
                "properties": event.properties,
                "timestamp": datetime.utcnow().isoformat(),
            }
            channel = RedisKeys.pubsub_events(str(event.org_id))
            await redis.publish(channel, json.dumps(payload, default=str))
        except Exception as pub_err:
            logger.warning("Redis publish failed (non-fatal): %s", pub_err)

        logger.info("Recorded analytics event %s type=%s", event_id, event.event_type)
        return EventResponse(id=event_id, status="recorded")

    except Exception as exc:
        logger.error("Failed to record event: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to record analytics event") from exc


# ── 8. CSV export ──


@app.get("/api/v1/analytics/export", tags=["analytics"])
async def export_csv(
    org_id: str = Query(...),
    entity: str = Query("conversations", description="conversations | tickets | events"),
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    limit: int = Query(10000, ge=1, le=50000),
):
    """Export raw data as a downloadable CSV file."""
    start = start_date or _default_start()
    end = end_date or _default_end()

    queries = {
        "conversations": """
            SELECT id, org_id, channel, direction, status, sentiment_score,
                   is_ai_handled, talk_duration_seconds, queue_wait_seconds,
                   transfer_count, created_at, ended_at
            FROM conversations
            WHERE org_id = :org
              AND created_at >= :start AND created_at < :end + INTERVAL '1 day'
            ORDER BY created_at DESC
            LIMIT :lim
        """,
        "tickets": """
            SELECT id, org_id, ticket_number, subject, status, priority,
                   category, sla_breach, created_at, first_response_at, resolved_at
            FROM tickets
            WHERE org_id = :org
              AND created_at >= :start AND created_at < :end + INTERVAL '1 day'
            ORDER BY created_at DESC
            LIMIT :lim
        """,
        "events": """
            SELECT id, org_id, event_type, event_category, actor_type,
                   numeric_value, created_at
            FROM analytics_events
            WHERE org_id = :org
              AND created_at >= :start AND created_at < :end + INTERVAL '1 day'
            ORDER BY created_at DESC
            LIMIT :lim
        """,
    }

    if entity not in queries:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entity '{entity}'. Choose from: {', '.join(queries.keys())}",
        )

    try:
        async with async_session_factory() as session:
            result = await session.execute(
                text(queries[entity]),
                {"org": org_id, "start": start, "end": end, "lim": limit},
            )
            rows = result.mappings().all()

        if not rows:
            raise HTTPException(status_code=404, detail="No data found for the given filters")

        # Build CSV in-memory
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: str(v) for k, v in row.items()})

        csv_content = output.getvalue()
        filename = f"{entity}_{org_id}_{start}_{end}.csv"

        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("CSV export failed: %s", exc)
        raise HTTPException(status_code=500, detail="Export failed") from exc


# ── Entrypoint ──

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8004, reload=True)
