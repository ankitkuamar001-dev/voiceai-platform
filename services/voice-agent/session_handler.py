"""Session Handler — Redis-backed per-call state management.

Tracks conversation metadata, sentiment history, turn counts, and
detects escalation triggers so the voice agent can decide when to
hand off to a human.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


# Shared utilities
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from shared.utils.database import RedisKeys, get_redis

logger = logging.getLogger("voice-agent.session")

# ── Configuration ──

SENTIMENT_ESCALATION_THRESHOLD = float(os.getenv("SENTIMENT_ESCALATION_THRESHOLD", "-0.5"))
MAX_TURNS_BEFORE_ESCALATION = int(os.getenv("MAX_TURNS_BEFORE_ESCALATION", "20"))
STATE_TTL_SECONDS = int(os.getenv("SESSION_STATE_TTL", "7200"))  # 2 hours


# ── Data Classes ──


@dataclass
class SessionState:
    """Mutable per-conversation state stored in Redis."""

    conversation_id: str
    customer_id: str | None = None
    customer_name: str | None = None
    customer_email: str | None = None
    sentiment_history: list[float] = field(default_factory=list)
    turn_count: int = 0
    escalation_status: str = "none"  # none | pending | escalated | resolved
    escalation_reason: str | None = None
    escalation_signals: list[str] = field(default_factory=list)
    intent_history: list[str] = field(default_factory=list)
    customer_tier: str = "standard"
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_activity_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # ── Computed properties ──

    @property
    def avg_sentiment(self) -> float:
        """Rolling average of recorded sentiment scores."""
        if not self.sentiment_history:
            return 0.0
        return sum(self.sentiment_history) / len(self.sentiment_history)

    @property
    def latest_sentiment(self) -> float:
        """Most recent sentiment score, or 0.0 if none recorded."""
        return self.sentiment_history[-1] if self.sentiment_history else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dictionary."""
        data = asdict(self)
        data["avg_sentiment"] = self.avg_sentiment
        data["latest_sentiment"] = self.latest_sentiment
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionState:
        """Deserialize from a dictionary (ignores computed fields)."""
        # Strip computed keys that aren't constructor args
        known_keys = {
            "conversation_id", "customer_id", "customer_name", "customer_email",
            "sentiment_history", "turn_count", "escalation_status",
            "escalation_reason", "escalation_signals", "intent_history",
            "customer_tier", "tags", "metadata", "started_at",
            "last_activity_at",
        }
        filtered = {k: v for k, v in data.items() if k in known_keys}
        return cls(**filtered)


# ── Persistence ──


async def save_state(state: SessionState) -> None:
    """Persist session state to Redis with TTL."""
    state.last_activity_at = datetime.now(timezone.utc).isoformat()
    redis = await get_redis()
    key = RedisKeys.conversation_state(state.conversation_id)
    await redis.setex(key, STATE_TTL_SECONDS, json.dumps(state.to_dict()))
    logger.debug("Saved state for conversation %s", state.conversation_id)


async def load_state(conversation_id: str) -> SessionState | None:
    """Load session state from Redis; returns None if not found."""
    redis = await get_redis()
    key = RedisKeys.conversation_state(conversation_id)
    raw = await redis.get(key)
    if raw is None:
        logger.debug("No state found for conversation %s", conversation_id)
        return None
    try:
        data = json.loads(raw)
        return SessionState.from_dict(data)
    except (json.JSONDecodeError, TypeError, KeyError) as exc:
        logger.error("Failed to parse state for %s: %s", conversation_id, exc)
        return None


async def delete_state(conversation_id: str) -> None:
    """Remove session state from Redis."""
    redis = await get_redis()
    key = RedisKeys.conversation_state(conversation_id)
    await redis.delete(key)
    logger.debug("Deleted state for conversation %s", conversation_id)


async def update_sentiment(conversation_id: str, score: float) -> SessionState | None:
    """Append a sentiment score to the conversation history and re-save."""
    state = await load_state(conversation_id)
    if state is None:
        logger.warning("Cannot update sentiment — no state for %s", conversation_id)
        return None
    state.sentiment_history.append(score)
    await save_state(state)
    return state


async def set_customer_info(
    conversation_id: str,
    *,
    customer_id: str | None = None,
    customer_name: str | None = None,
    customer_email: str | None = None,
) -> SessionState | None:
    """Attach customer details to the session after identification."""
    state = await load_state(conversation_id)
    if state is None:
        return None
    if customer_id is not None:
        state.customer_id = customer_id
    if customer_name is not None:
        state.customer_name = customer_name
    if customer_email is not None:
        state.customer_email = customer_email
    await save_state(state)
    return state


# ── Escalation Detection ──


def detect_escalation(state: SessionState) -> bool:
    """Determine whether the conversation should be escalated.

    Triggers:
      1. Latest sentiment below threshold (e.g. < -0.5)
      2. Turn count exceeds maximum (e.g. > 20)
      3. Escalation already requested explicitly
    """
    if state.escalation_status in ("pending", "escalated"):
        return False  # already flagged

    # Sentiment trigger
    if state.latest_sentiment < SENTIMENT_ESCALATION_THRESHOLD:
        logger.info(
            "Escalation trigger: sentiment %.2f < %.2f for %s",
            state.latest_sentiment,
            SENTIMENT_ESCALATION_THRESHOLD,
            state.conversation_id,
        )
        state.escalation_reason = (
            f"Negative sentiment detected (score: {state.latest_sentiment:.2f})"
        )
        return True

    # Turn-count trigger
    if state.turn_count > MAX_TURNS_BEFORE_ESCALATION:
        logger.info(
            "Escalation trigger: turn_count %d > %d for %s",
            state.turn_count,
            MAX_TURNS_BEFORE_ESCALATION,
            state.conversation_id,
        )
        state.escalation_reason = (
            f"Extended conversation ({state.turn_count} turns)"
        )
        return True

    return False
