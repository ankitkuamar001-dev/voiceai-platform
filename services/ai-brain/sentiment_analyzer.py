"""Sentiment Analyzer — OpenAI-powered sentiment scoring.

Returns:
  • score: -1.0 (very negative) to 1.0 (very positive)
  • emotion: happy | neutral | frustrated | angry | confused
  • should_escalate: True when the customer seems highly upset
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

logger = logging.getLogger("ai-brain.sentiment")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ESCALATION_THRESHOLD = float(os.getenv("SENTIMENT_ESCALATION_THRESHOLD", "-0.5"))

VALID_EMOTIONS = {"happy", "neutral", "frustrated", "angry", "confused"}


class SentimentAnalyzer:
    """Analyze customer sentiment using an OpenAI chat model."""

    def __init__(self) -> None:
        self._llm = ChatOpenAI(
            model="gpt-4o-mini",  # fast + cheap for classification
            temperature=0.0,
            openai_api_key=OPENAI_API_KEY,
        )

    async def analyze(self, text: str) -> dict[str, Any]:
        """Analyze sentiment of the given text.

        Returns
        -------
        dict
            score : float in [-1.0, 1.0]
            emotion : str — one of happy, neutral, frustrated, angry, confused
            should_escalate : bool
        """
        if not text or not text.strip():
            return {"score": 0.0, "emotion": "neutral", "should_escalate": False}

        system = (
            "You are a sentiment analysis engine for a customer-support platform.\n"
            "Analyze the customer's message and respond with ONLY valid JSON:\n"
            "{\n"
            '  "score": <float from -1.0 (very negative) to 1.0 (very positive)>,\n'
            '  "emotion": "<one of: happy, neutral, frustrated, angry, confused>",\n'
            '  "should_escalate": <true if customer is very upset or requesting a manager>\n'
            "}\n"
            "Be precise. Consider tone, word choice, punctuation, and caps."
        )

        messages = [
            SystemMessage(content=system),
            HumanMessage(content=f"Customer message: {text}"),
        ]

        try:
            response = await self._llm.ainvoke(messages)
            raw = response.content if hasattr(response, "content") else str(response)
            parsed = json.loads(raw)

            score = max(-1.0, min(1.0, float(parsed.get("score", 0.0))))
            emotion = parsed.get("emotion", "neutral")
            if emotion not in VALID_EMOTIONS:
                emotion = "neutral"

            # Determine escalation
            explicit_escalate = bool(parsed.get("should_escalate", False))
            threshold_escalate = score < ESCALATION_THRESHOLD

            return {
                "score": score,
                "emotion": emotion,
                "should_escalate": explicit_escalate or threshold_escalate,
            }
        except json.JSONDecodeError:
            logger.warning("Failed to parse sentiment JSON, returning defaults")
            return {"score": 0.0, "emotion": "neutral", "should_escalate": False}
        except Exception as exc:
            logger.error("Sentiment analysis error: %s", exc)
            return {"score": 0.0, "emotion": "neutral", "should_escalate": False}

    async def analyze_batch(self, texts: list[str]) -> list[dict[str, Any]]:
        """Analyze sentiment of multiple texts (sequential for simplicity)."""
        results = []
        for text in texts:
            result = await self.analyze(text)
            results.append(result)
        return results
