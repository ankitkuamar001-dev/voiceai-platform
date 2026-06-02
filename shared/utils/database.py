"""Shared database utilities — async SQLAlchemy + Redis connection management."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://voiceai:changeme_pg_password@localhost:5432/voiceai",
)
REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://:changeme_redis_password@localhost:6379/0",
)

# ── SQLAlchemy Async Engine ──

engine_kwargs = {
    "echo": os.getenv("DEBUG", "false").lower() == "true",
    "pool_pre_ping": True,
    "pool_recycle": 3600,
}

if not DATABASE_URL.startswith("sqlite"):
    engine_kwargs["pool_size"] = 20
    engine_kwargs["max_overflow"] = 10

engine = create_async_engine(DATABASE_URL, **engine_kwargs)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async DB session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for use outside FastAPI (e.g., scripts, agents)."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Redis Connection Pool ──

_redis_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Get or create a Redis connection from the pool."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
    return _redis_pool


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.close()
        _redis_pool = None


# ── Redis Key Helpers ──


class RedisKeys:
    """Centralized Redis key patterns."""

    @staticmethod
    def session(session_id: str) -> str:
        return f"session:{session_id}"

    @staticmethod
    def agent_status(org_id: str, agent_id: str) -> str:
        return f"agent:{org_id}:{agent_id}:status"

    @staticmethod
    def agents_available(org_id: str) -> str:
        return f"agents:available:{org_id}"

    @staticmethod
    def queue_calls(org_id: str) -> str:
        return f"queue:calls:{org_id}"

    @staticmethod
    def queue_stats(org_id: str) -> str:
        return f"queue:stats:{org_id}"

    @staticmethod
    def dashboard(org_id: str) -> str:
        return f"dashboard:{org_id}"

    @staticmethod
    def metrics_daily(org_id: str, date: str) -> str:
        return f"metrics:daily:{org_id}:{date}"

    @staticmethod
    def metrics_hourly(org_id: str, hour: str) -> str:
        return f"metrics:hourly:{org_id}:{hour}"

    @staticmethod
    def ratelimit(identifier: str, endpoint: str) -> str:
        return f"ratelimit:{identifier}:{endpoint}"

    @staticmethod
    def cache_permissions(org_id: str, user_id: str) -> str:
        return f"cache:permissions:{org_id}:{user_id}"

    @staticmethod
    def pubsub_events(org_id: str) -> str:
        return f"events:{org_id}"

    @staticmethod
    def conversation_state(conversation_id: str) -> str:
        return f"conversation:state:{conversation_id}"
