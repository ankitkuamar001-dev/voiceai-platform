"""LLM Orchestrator — LangChain-based language-model orchestration.

Provides:
  • Response generation with conversation memory
  • Intent classification
  • Conversation summarization
  • Streaming response support (via async generator)
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, AsyncIterator

from langchain_openai import ChatOpenAI
from langchain.schema import AIMessage, HumanMessage, SystemMessage

logger = logging.getLogger("ai-brain.llm")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL_NAME = os.getenv("LLM_MODEL", "gpt-4o")
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.4"))
MAX_MEMORY_MESSAGES = int(os.getenv("MAX_MEMORY_MESSAGES", "20"))

# Load system prompt from file
_PROMPT_PATH = Path(os.path.dirname(__file__)) / "prompts" / "system_prompt.txt"
_DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful customer-support assistant. "
    "Be professional, concise, and empathetic."
)

INTENT_CATEGORIES = [
    "billing",
    "technical",
    "orders",
    "general",
    "escalation",
    "account",
    "returns",
    "shipping",
]


def _load_system_prompt() -> str:
    """Load the system prompt from disk, falling back to a default."""
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logger.warning(
            "System prompt file not found at %s — using default", _PROMPT_PATH
        )
        return _DEFAULT_SYSTEM_PROMPT


class LLMOrchestrator:
    """Orchestrates OpenAI LLM calls via LangChain."""

    def __init__(self) -> None:
        self._llm = ChatOpenAI(
            model=MODEL_NAME,
            temperature=TEMPERATURE,
            openai_api_key=OPENAI_API_KEY,
            streaming=True,
        )
        self._system_prompt = _load_system_prompt()
        # In-memory conversation buffers keyed by conversation_id
        self._buffers: dict[str, list[dict[str, str]]] = {}

    # ── Response generation ──

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        conversation_id: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Generate a response given a list of messages.

        Parameters
        ----------
        messages : list of {"role": "user"|"assistant"|"system", "content": str}
        system_prompt : override for the default system prompt
        conversation_id : optional key for conversation memory buffer
        tools : optional tool schemas (currently unused — reserved for LangGraph)

        Returns
        -------
        dict with keys: response, intent (optional), confidence (optional), metadata
        """
        prompt = system_prompt or self._system_prompt

        # Build LangChain message list
        lc_messages = [SystemMessage(content=prompt)]

        # Prepend buffer if we have conversation history
        if conversation_id and conversation_id in self._buffers:
            for m in self._buffers[conversation_id][-MAX_MEMORY_MESSAGES:]:
                lc_messages.append(self._to_lc_message(m))

        # Append current turn
        for m in messages:
            lc_messages.append(self._to_lc_message(m))

        # Invoke the LLM
        response = await self._llm.ainvoke(lc_messages)
        response_text = (
            response.content if hasattr(response, "content") else str(response)
        )

        # Update buffer
        if conversation_id is not None:
            if conversation_id not in self._buffers:
                self._buffers[conversation_id] = []
            for m in messages:
                self._buffers[conversation_id].append(m)
            self._buffers[conversation_id].append(
                {"role": "assistant", "content": response_text}
            )
            # Trim to max size
            self._buffers[conversation_id] = self._buffers[conversation_id][
                -MAX_MEMORY_MESSAGES:
            ]

        return {
            "response": response_text,
            "metadata": {"model": MODEL_NAME},
        }

    # ── Streaming ──

    async def generate_response_stream(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """Yield response tokens as they arrive (streaming)."""
        prompt = system_prompt or self._system_prompt
        lc_messages = [SystemMessage(content=prompt)]
        for m in messages:
            lc_messages.append(self._to_lc_message(m))

        async for chunk in self._llm.astream(lc_messages):
            token = chunk.content if hasattr(chunk, "content") else str(chunk)
            if token:
                yield token

    # ── Intent classification ──

    async def classify_intent(self, text: str) -> dict[str, Any]:
        """Classify user text into an intent category.

        Returns dict with: intent, confidence, sub_intents.
        """
        classification_prompt = (
            "You are an intent classifier for a customer-support platform.\n"
            f"Categories: {', '.join(INTENT_CATEGORIES)}\n\n"
            "Respond with ONLY valid JSON: "
            '{"intent": "<category>", "confidence": <0.0-1.0>, "sub_intents": [...]}\n\n'
            f"User message: {text}"
        )

        lc_messages = [
            SystemMessage(
                content="You classify customer intents. Respond only with JSON."
            ),
            HumanMessage(content=classification_prompt),
        ]

        response = await self._llm.ainvoke(lc_messages)
        raw = response.content if hasattr(response, "content") else str(response)

        try:
            parsed = json.loads(raw)
            return {
                "intent": parsed.get("intent", "general"),
                "confidence": float(parsed.get("confidence", 0.5)),
                "sub_intents": parsed.get("sub_intents", []),
            }
        except (json.JSONDecodeError, ValueError):
            logger.warning("Failed to parse intent JSON: %s", raw)
            return {"intent": "general", "confidence": 0.3, "sub_intents": []}

    # ── Summarization ──

    async def summarize(self, messages: list[dict[str, str]]) -> str:
        """Generate a concise summary of a conversation."""
        if not messages:
            return "No conversation to summarize."

        transcript = "\n".join(
            f"{m.get('role', 'unknown').upper()}: {m.get('content', '')}"
            for m in messages
        )

        lc_messages = [
            SystemMessage(
                content=(
                    "You summarize customer-support conversations. "
                    "Produce a concise 2-3 sentence summary capturing: "
                    "the customer's issue, actions taken, and outcome."
                )
            ),
            HumanMessage(content=f"Summarize this conversation:\n\n{transcript}"),
        ]

        response = await self._llm.ainvoke(lc_messages)
        return response.content if hasattr(response, "content") else str(response)

    # ── Helpers ──

    @staticmethod
    def _to_lc_message(msg: dict[str, str]):
        """Convert a role/content dict to a LangChain message object."""
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            return SystemMessage(content=content)
        elif role == "assistant":
            return AIMessage(content=content)
        else:
            return HumanMessage(content=content)

    def clear_buffer(self, conversation_id: str) -> None:
        """Clear the memory buffer for a conversation."""
        self._buffers.pop(conversation_id, None)
