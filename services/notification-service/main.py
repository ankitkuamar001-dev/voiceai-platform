"""Notification Service — Real-time WebSocket event hub for the AI Voice platform.

Manages per-organisation WebSocket connections, JWT-authenticated handshakes,
heartbeat ping/pong, automatic dead-connection cleanup, and cross-instance
event broadcasting via Redis Pub/Sub.

Run:
    uvicorn main:app --host 0.0.0.0 --port 8005 --reload
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from pydantic import BaseModel, Field

# ── Path bootstrap ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, "/app")

from shared.schemas.models import WSEvent
from shared.utils.database import RedisKeys, close_redis, get_redis

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("notification-service")

# ── Config ──
JWT_SECRET = os.getenv("JWT_SECRET", "changeme_jwt_secret_key_32_chars!")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
HEARTBEAT_INTERVAL = 30  # seconds
CLEANUP_INTERVAL = 60  # seconds

# Valid event types this service recognises
VALID_EVENT_TYPES = {
    "call.started",
    "call.ended",
    "ticket.created",
    "ticket.updated",
    "escalation.requested",
    "handoff.requested",
    "handoff.accepted",
    "handoff.rejected",
    "handoff.completed",
    "handoff.queue_update",
    "agent.status_changed",
    "metrics.updated",
}


# ── Pydantic schemas ──


class BroadcastRequest(BaseModel):
    org_id: str
    event_type: str
    data: dict[str, Any] = Field(default_factory=dict)


class SendRequest(BaseModel):
    org_id: str
    user_id: str
    event_type: str
    data: dict[str, Any] = Field(default_factory=dict)


class ConnectionInfo(BaseModel):
    org_id: str
    user_id: str
    connected_at: str
    last_pong: str


class ConnectionsResponse(BaseModel):
    connections: list[ConnectionInfo] = Field(default_factory=list)
    total: int = 0


class HealthResponse(BaseModel):
    status: str = "healthy"
    service: str = "notification-service"
    timestamp: str
    active_connections: int = 0


# ── Connection Manager ──


class _Client:
    """Represents a single authenticated WebSocket connection."""

    __slots__ = ("ws", "org_id", "user_id", "connected_at", "last_pong")

    def __init__(self, ws: WebSocket, org_id: str, user_id: str):
        self.ws = ws
        self.org_id = org_id
        self.user_id = user_id
        self.connected_at = time.time()
        self.last_pong = time.time()


class ConnectionManager:
    """Thread-safe manager that tracks WebSocket clients grouped by org_id."""

    def __init__(self):
        # org_id → list[_Client]
        self._connections: dict[str, list[_Client]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, client: _Client) -> None:
        async with self._lock:
            self._connections.setdefault(client.org_id, []).append(client)
        logger.info(
            "WS connected: org=%s user=%s (total=%d)",
            client.org_id,
            client.user_id,
            self.total,
        )

    async def disconnect(self, client: _Client) -> None:
        async with self._lock:
            clients = self._connections.get(client.org_id, [])
            if client in clients:
                clients.remove(client)
            if not clients:
                self._connections.pop(client.org_id, None)
        logger.info(
            "WS disconnected: org=%s user=%s (total=%d)",
            client.org_id,
            client.user_id,
            self.total,
        )

    async def broadcast(self, org_id: str, message: str) -> None:
        """Send *message* to every connection in *org_id*."""
        async with self._lock:
            clients = list(self._connections.get(org_id, []))

        dead: list[_Client] = []
        for client in clients:
            try:
                await client.ws.send_text(message)
            except Exception:
                dead.append(client)

        for client in dead:
            await self.disconnect(client)

    async def send_to_user(self, org_id: str, user_id: str, message: str) -> int:
        """Send to a specific user; returns number of deliveries."""
        async with self._lock:
            clients = [
                c
                for c in self._connections.get(org_id, [])
                if c.user_id == user_id
            ]

        sent = 0
        dead: list[_Client] = []
        for client in clients:
            try:
                await client.ws.send_text(message)
                sent += 1
            except Exception:
                dead.append(client)

        for client in dead:
            await self.disconnect(client)

        return sent

    async def cleanup_dead(self) -> int:
        """Remove connections that haven't responded to pings in 3 intervals."""
        cutoff = time.time() - HEARTBEAT_INTERVAL * 3
        removed = 0
        async with self._lock:
            for org_id in list(self._connections.keys()):
                alive: list[_Client] = []
                for c in self._connections[org_id]:
                    if c.last_pong < cutoff:
                        try:
                            await c.ws.close(code=1001, reason="ping timeout")
                        except Exception:
                            pass
                        removed += 1
                        logger.info(
                            "Cleaned up dead WS: org=%s user=%s",
                            c.org_id,
                            c.user_id,
                        )
                    else:
                        alive.append(c)
                if alive:
                    self._connections[org_id] = alive
                else:
                    del self._connections[org_id]
        return removed

    def get_connections_info(self, org_id: str | None = None) -> list[ConnectionInfo]:
        result: list[ConnectionInfo] = []
        orgs = [org_id] if org_id else list(self._connections.keys())
        for oid in orgs:
            for c in self._connections.get(oid, []):
                result.append(
                    ConnectionInfo(
                        org_id=c.org_id,
                        user_id=c.user_id,
                        connected_at=datetime.utcfromtimestamp(c.connected_at).isoformat(),
                        last_pong=datetime.utcfromtimestamp(c.last_pong).isoformat(),
                    )
                )
        return result

    @property
    def total(self) -> int:
        return sum(len(v) for v in self._connections.values())


manager = ConnectionManager()


# ── JWT helpers ──


def _verify_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT; returns the payload dict."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if "sub" not in payload:
            raise ValueError("Missing 'sub' claim")
        return payload
    except JWTError as exc:
        raise ValueError(f"Invalid token: {exc}") from exc


# ── Background tasks ──


async def _heartbeat_loop():
    """Periodically ping all connected WebSockets."""
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL)
        for clients in list(manager._connections.values()):
            for client in list(clients):
                try:
                    await client.ws.send_json({"type": "ping", "ts": time.time()})
                except Exception:
                    await manager.disconnect(client)


async def _cleanup_loop():
    """Periodically prune dead connections."""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        removed = await manager.cleanup_dead()
        if removed:
            logger.info("Cleanup removed %d dead connection(s)", removed)


async def _redis_subscriber():
    """Subscribe to Redis Pub/Sub and forward events to local WebSocket clients.

    Subscribes to ``events:*`` pattern so every org's channel is covered.
    On message, determine the org_id from the channel name and broadcast.
    """
    while True:
        try:
            redis = await get_redis()
            pubsub = redis.pubsub()
            await pubsub.psubscribe("events:*")
            logger.info("Redis Pub/Sub subscriber started (pattern: events:*)")

            async for message in pubsub.listen():
                if message["type"] not in ("pmessage",):
                    continue

                channel: str = message.get("channel", "")
                data_raw: str = message.get("data", "{}")

                # Channel format is  events:<org_id>
                org_id = channel.split(":", 1)[1] if ":" in channel else None
                if not org_id:
                    continue

                logger.debug("Redis event on %s: %s", channel, data_raw[:200])
                await manager.broadcast(org_id, data_raw)

        except asyncio.CancelledError:
            logger.info("Redis subscriber cancelled")
            break
        except Exception as exc:
            logger.error("Redis subscriber error (reconnecting in 5 s): %s", exc)
            await asyncio.sleep(5)


# ── Lifespan ──

_bg_tasks: list[asyncio.Task] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting notification-service …")

    # Verify Redis connectivity
    try:
        redis = await get_redis()
        await redis.ping()
        logger.info("Redis connected ✓")
    except Exception as exc:
        logger.warning("Redis unavailable — Pub/Sub disabled: %s", exc)

    # Launch background loops
    _bg_tasks.append(asyncio.create_task(_heartbeat_loop()))
    _bg_tasks.append(asyncio.create_task(_cleanup_loop()))
    _bg_tasks.append(asyncio.create_task(_redis_subscriber()))

    yield

    logger.info("Shutting down notification-service …")
    for task in _bg_tasks:
        task.cancel()
    await asyncio.gather(*_bg_tasks, return_exceptions=True)
    _bg_tasks.clear()
    await close_redis()


# ── App ──

app = FastAPI(
    title="Notification Service",
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


# ── Routes ──


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    return HealthResponse(
        status="healthy",
        service="notification-service",
        timestamp=datetime.utcnow().isoformat(),
        active_connections=manager.total,
    )


# ── WebSocket endpoint ──


@app.websocket("/ws/{org_id}")
async def websocket_endpoint(websocket: WebSocket, org_id: str):
    """Authenticated WebSocket connection per organisation.

    Clients connect with ``?token=<JWT>`` query param.  After authentication
    the connection receives real-time events for the given *org_id*.
    """
    # 1. Extract & verify JWT from query params
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing token")
        return

    try:
        payload = _verify_token(token)
    except ValueError as exc:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=str(exc))
        return

    user_id: str = payload["sub"]
    token_org: str | None = payload.get("org_id")

    # Optional: verify the JWT org matches the path
    if token_org and token_org != org_id:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="org_id mismatch",
        )
        return

    # 2. Accept connection
    await websocket.accept()
    client = _Client(ws=websocket, org_id=org_id, user_id=user_id)
    await manager.connect(client)

    # Send welcome
    await websocket.send_json(
        {
            "type": "connection.established",
            "data": {
                "org_id": org_id,
                "user_id": user_id,
                "message": "Connected to notification service",
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
    )

    # 3. Listen for client messages (pong, etc.)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type", "")

            if msg_type == "pong":
                client.last_pong = time.time()
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong", "ts": time.time()})
            else:
                logger.debug("WS message from user=%s type=%s", user_id, msg_type)

    except WebSocketDisconnect:
        logger.info("WS client disconnected: org=%s user=%s", org_id, user_id)
    except Exception as exc:
        logger.error("WS error org=%s user=%s: %s", org_id, user_id, exc)
    finally:
        await manager.disconnect(client)


# ── REST broadcast / send ──


@app.post("/api/v1/notifications/broadcast", tags=["notifications"])
async def broadcast_event(req: BroadcastRequest):
    """Broadcast an event to all WebSocket connections in an organisation.

    Also publishes to Redis Pub/Sub so other service instances can relay it.
    """
    if req.event_type not in VALID_EVENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown event_type '{req.event_type}'. Valid: {sorted(VALID_EVENT_TYPES)}",
        )

    event = WSEvent(
        type=req.event_type,
        data=req.data,
        org_id=UUID(req.org_id) if req.org_id else None,
    )
    payload = event.model_dump_json()

    # Local broadcast
    await manager.broadcast(req.org_id, payload)

    # Publish to Redis for cross-instance delivery
    try:
        redis = await get_redis()
        channel = RedisKeys.pubsub_events(req.org_id)
        await redis.publish(channel, payload)
    except Exception as exc:
        logger.warning("Redis publish failed (non-fatal): %s", exc)

    logger.info("Broadcast %s to org=%s", req.event_type, req.org_id)
    return {"status": "broadcast", "event_type": req.event_type, "org_id": req.org_id}


@app.post("/api/v1/notifications/send", tags=["notifications"])
async def send_to_user(req: SendRequest):
    """Send an event to a specific user's WebSocket connection(s)."""
    if req.event_type not in VALID_EVENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown event_type '{req.event_type}'. Valid: {sorted(VALID_EVENT_TYPES)}",
        )

    event = WSEvent(
        type=req.event_type,
        data=req.data,
        org_id=UUID(req.org_id) if req.org_id else None,
    )
    payload = event.model_dump_json()

    delivered = await manager.send_to_user(req.org_id, req.user_id, payload)

    if delivered == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No active connections for user {req.user_id} in org {req.org_id}",
        )

    logger.info(
        "Sent %s to user=%s org=%s (%d conn(s))",
        req.event_type,
        req.user_id,
        req.org_id,
        delivered,
    )
    return {
        "status": "sent",
        "event_type": req.event_type,
        "user_id": req.user_id,
        "connections_delivered": delivered,
    }


@app.get(
    "/api/v1/notifications/connections",
    response_model=ConnectionsResponse,
    tags=["notifications"],
)
async def list_connections(
    org_id: str = Query(default=None, description="Filter by org (optional)"),
):
    """List all active WebSocket connections, optionally filtered by org_id."""
    conns = manager.get_connections_info(org_id=org_id)
    return ConnectionsResponse(connections=conns, total=len(conns))


# ── Entrypoint ──

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8005, reload=True)
