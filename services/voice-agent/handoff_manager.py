"""Human Handoff System — Agent Queue and Context Handover."""

import json
import logging
import uuid
import os
import sys
from typing import List, Dict, Any, Optional

import redis.asyncio as aioredis
from sqlalchemy import text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from shared.utils.database import async_session_factory, get_redis

logger = logging.getLogger("voice-agent.handoff")

NOTIFICATION_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:8005")

class AgentQueue:
    """Manages queues of customers waiting for human agents."""
    
    def __init__(self, org_id: str):
        self.org_id = org_id

    @property
    def queue_key(self):
        return f"handoff:queue:{self.org_id}"

    async def enqueue(self, handoff_request_id: str, priority: int = 3) -> int:
        """Add request to queue and return position."""
        redis = await get_redis()
        # Use priority as score in sorted set, ties broken by timestamp (in real system)
        # For simplicity, just appending to list
        await redis.rpush(self.queue_key, handoff_request_id)
        pos = await redis.llen(self.queue_key)
        return pos

    async def get_position(self, handoff_request_id: str) -> int:
        """Get position in queue."""
        redis = await get_redis()
        queue = await redis.lrange(self.queue_key, 0, -1)
        try:
            return queue.index(handoff_request_id.encode()) + 1
        except ValueError:
            return 0


async def request_handoff(
    org_id: str, 
    conversation_id: str, 
    customer_id: Optional[str] = None,
    escalation_id: Optional[str] = None
) -> Dict[str, Any]:
    """Initiates a human handoff, creates DB record, adds to queue."""
    
    # 1. Create DB record
    handoff_id = None
    async with async_session_factory() as session:
        try:
            result = await session.execute(
                text("""
                    INSERT INTO handoff_requests (org_id, conversation_id, customer_id, escalation_id)
                    VALUES (:org, :conv, :cust, :esc)
                    RETURNING id
                """),
                {"org": org_id, "conv": conversation_id, "cust": customer_id, "esc": escalation_id}
            )
            await session.commit()
            handoff_id = str(result.scalar())
        except Exception as exc:
            logger.error("Failed to insert handoff request: %s", exc)
            raise
            
    # 2. Add to Queue
    queue = AgentQueue(org_id)
    position = await queue.enqueue(handoff_id)
    
    # 3. Broadcast to Agents
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{NOTIFICATION_URL}/api/v1/notifications/broadcast",
                json={
                    "org_id": org_id,
                    "event_type": "handoff.requested",
                    "payload": {
                        "handoff_id": handoff_id,
                        "conversation_id": conversation_id,
                        "position": position
                    }
                }
            )
    except Exception as exc:
        logger.warning("Failed to notify agents: %s", exc)
        
    return {
        "status": "queued",
        "handoff_id": handoff_id,
        "position": position,
        "estimated_wait_sec": position * 120 # rough estimate
    }
