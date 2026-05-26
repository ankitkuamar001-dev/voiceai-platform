"""Voice Agent — LiveKit Agents v1.5+ application.

A real-time AI voice customer-support agent backed by:
  • Silero  VAD
  • Deepgram STT
  • OpenAI  GPT-4o LLM
  • Cartesia TTS

Conversation state is persisted in Redis; every turn is logged to the
ai-brain service via HTTP.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# ── Path setup for shared modules ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from livekit.agents import AgentSession, Agent, RoomInputOptions, cli, llm
from livekit.agents.voice import VoiceSession
from livekit.plugins import openai, silero, deepgram, cartesia

from agent_tools import (
    lookup_order,
    create_ticket,
    check_account,
    request_human_handoff,
    process_refund,
    search_knowledge_base,
    book_appointment,
    conversation_id_ctx,
    org_id_ctx
)
from session_handler import SessionState, save_state, load_state
from escalation_engine import EscalationEngine
from recording_manager import start_recording, stop_recording

logger = logging.getLogger("voice-agent")
logger.setLevel(logging.INFO)

AI_BRAIN_URL = os.getenv("AI_BRAIN_URL", "http://localhost:8001")


# ── LLM tool definitions ──

TOOL_DEFINITIONS: list[llm.FunctionTool] = [
    llm.FunctionTool(
        name="lookup_order",
        description="Look up the status and details of a customer order by its order ID.",
        parameters={
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The order identifier (e.g. ORD-12345).",
                },
            },
            "required": ["order_id"],
        },
        callable=lookup_order,
    ),
    llm.FunctionTool(
        name="create_ticket",
        description="Create a support ticket for the customer.",
        parameters={
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "Short summary of the issue.",
                },
                "description": {
                    "type": "string",
                    "description": "Full description of the issue.",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"],
                    "description": "Priority level of the ticket.",
                },
            },
            "required": ["subject", "description", "priority"],
        },
        callable=create_ticket,
    ),
    llm.FunctionTool(
        name="check_account",
        description="Retrieve customer account details by email.",
        parameters={
            "type": "object",
            "properties": {
                "customer_email": {
                    "type": "string",
                    "description": "Customer's email address.",
                },
            },
            "required": ["customer_email"],
        },
        callable=check_account,
    ),
    llm.FunctionTool(
        name="request_human_handoff",
        description="Transfer the call to a human agent.",
        parameters={
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Reason for the handoff.",
                },
            },
            "required": ["reason"],
        },
        callable=request_human_handoff,
    ),
    llm.FunctionTool(
        name="process_refund",
        description="Process a refund for an order.",
        parameters={
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The order identifier.",
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for the refund.",
                },
            },
            "required": ["order_id", "reason"],
        },
        callable=process_refund,
    ),
    llm.FunctionTool(
        name="search_knowledge_base",
        description="Search the knowledge base for relevant information.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                },
            },
            "required": ["query"],
        },
        callable=search_knowledge_base,
    ),
    llm.FunctionTool(
        name="book_appointment",
        description="Book an appointment or callback for the customer.",
        parameters={
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Preferred date in ISO 8601 format.",
                },
                "time": {
                    "type": "string",
                    "description": "Preferred time (HH:MM, 24-hour).",
                },
                "reason": {
                    "type": "string",
                    "description": "Purpose of the appointment.",
                },
            },
            "required": ["date", "time", "reason"],
        },
        callable=book_appointment,
    ),
]


SYSTEM_PROMPT = """\
You are a professional customer support agent for our company. \
Be warm, concise, and helpful. When you know the customer's name, \
use it naturally. Ask clarifying questions before taking actions. \
Always confirm with the customer before executing any tool \
(refund, ticket creation, etc.). If you don't know an answer, \
say so honestly and offer to connect them with a specialist. \
Never fabricate order details, account info, or policies.\
"""


# ── Voice Agent ──


class CustomerSupportAgent(Agent):
    """LiveKit voice agent for real-time customer support."""

    def __init__(self) -> None:
        super().__init__(
            instructions=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
        )
        self._conversation_id: str = str(uuid.uuid4())
        self._org_id: str = os.getenv("DEFAULT_ORG_ID", "00000000-0000-0000-0000-000000000000")
        self._state: SessionState | None = None
        self._egress_id: str | None = None
        self._escalation_engine = EscalationEngine(self._org_id)

    # ── lifecycle hooks ──

    async def on_enter(self) -> None:
        """Called when the agent joins the room."""
        # Set context variables for tools
        conversation_id_ctx.set(self._conversation_id)
        org_id_ctx.set(self._org_id)
        
        logger.info("Agent entered room – conversation %s", self._conversation_id)
        self._state = SessionState(conversation_id=self._conversation_id)
        await save_state(self._state)
        await self._notify_brain("conversation_start", {
            "conversation_id": self._conversation_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
        })
        
        # Start LiveKit recording
        # self.room is available on the Agent instance once connected
        if hasattr(self, "room") and self.room.name:
            self._egress_id = await start_recording(self.room.name, self._org_id)

    async def on_exit(self) -> None:
        """Called when the agent leaves the room."""
        logger.info("Agent exiting room – conversation %s", self._conversation_id)
        if self._state:
            await self._notify_brain("conversation_end", {
                "conversation_id": self._conversation_id,
                "turn_count": self._state.turn_count,
                "ended_at": datetime.now(timezone.utc).isoformat(),
            })
            
        if self._egress_id:
            await stop_recording(self._egress_id)

    async def on_user_turn(self, turn: llm.ChatMessage) -> None:
        """Fires after each user utterance is transcribed."""
        text = turn.content if isinstance(turn.content, str) else str(turn.content)
        logger.info("[USER] %s", text)

        if self._state:
            self._state.turn_count += 1
            await save_state(self._state)

        # Log the user message to ai-brain
        await self._log_message(text, sender_type="customer")

        # Check for escalation triggers
        if self._state:
            # Note: We would normally fetch sentiment from AI Brain here
            # For brevity, we mock a sentiment score and intent
            mock_sentiment = 0.5
            mock_intent = "inquiry"
            self._state.sentiment_history.append(mock_sentiment)
            self._state.intent_history.append(mock_intent)
            
            decision = self._escalation_engine.evaluate(
                turn_count=self._state.turn_count,
                sentiment_scores=self._state.sentiment_history,
                intent_history=self._state.intent_history,
                latest_user_utterance=text,
                customer_tier=self._state.customer_tier
            )
            
            if decision.should_escalate and self._state.escalation_status not in ("pending", "escalated"):
                logger.warning("Escalation triggered for conversation %s: %s", self._conversation_id, decision.reason)
                self._state.escalation_status = "pending"
                self._state.escalation_reason = decision.reason
                self._state.escalation_signals = decision.signals
                await save_state(self._state)
                
                # Auto-trigger handoff tool via the agent (inject system message)
                # This makes the LLM gracefully acknowledge and transfer
                self.chat_ctx.messages.append(
                    llm.ChatMessage(
                        role="system",
                        content=f"SYSTEM INSTRUCTION: The escalation engine has triggered a human handoff due to {decision.reason}. Immediately call the request_human_handoff tool, explaining to the user that you are transferring them to a live agent."
                    )
                )

    async def on_agent_turn(self, turn: llm.ChatMessage) -> None:
        """Fires after the agent produces a response."""
        text = turn.content if isinstance(turn.content, str) else str(turn.content)
        logger.info("[AGENT] %s", text)

        # Log the agent message to ai-brain
        await self._log_message(text, sender_type="ai_bot")

    # ── helpers ──

    async def _log_message(self, content: str, sender_type: str) -> None:
        """POST a message record to the ai-brain service."""
        import httpx

        payload = {
            "content": content,
            "content_type": "text",
            "sender_type": sender_type,
            "conversation_id": self._conversation_id,
            "org_id": os.getenv("DEFAULT_ORG_ID", "00000000-0000-0000-0000-000000000000"),
            "sequence_num": self._state.turn_count if self._state else 0,
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{AI_BRAIN_URL}/api/v1/conversations/{self._conversation_id}/messages",
                    json=payload,
                )
        except Exception as exc:
            logger.error("Failed to log message to ai-brain: %s", exc)

    async def _notify_brain(self, event: str, data: dict[str, Any]) -> None:
        """Send a lifecycle event to ai-brain."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{AI_BRAIN_URL}/api/v1/ai/chat",
                    json={"event": event, **data},
                )
        except Exception as exc:
            logger.error("Failed to notify ai-brain (%s): %s", event, exc)


# ── Entrypoint callback for livekit-agents CLI ──


async def entrypoint(session: AgentSession):
    """Called by the LiveKit Agents framework when a new room session starts."""

    logger.info("Starting new voice session")

    agent = CustomerSupportAgent()

    session.start(
        agent=agent,
        room_input_options=RoomInputOptions(
            # Audio pipeline configuration
            vad=silero.VAD.load(),
            stt=deepgram.STT(
                model="nova-2",
                language="en-US",
            ),
            llm=openai.LLM(
                model="gpt-4o",
                temperature=0.4,
            ),
            tts=cartesia.TTS(
                model_id="sonic-english",
                voice="professional-female",  # warm, clear support voice
            ),
        ),
    )

    # Greet the caller
    await session.say(
        "Hello! Thank you for calling. My name is Ava, your virtual support assistant. "
        "How can I help you today?"
    )


# ── CLI runner ──

if __name__ == "__main__":
    cli.run_app(entrypoint)
