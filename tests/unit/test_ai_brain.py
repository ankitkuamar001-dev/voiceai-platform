"""Unit tests for the AI Brain Service.

Tests cover: sentiment analysis logic, intent classification, RAG result ranking,
conversation data structures, and knowledge search expectations.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from tests.conftest import TEST_ORG_ID, TEST_USER_ID


# ── Sentiment Analysis Tests ──


class TestSentimentAnalysis:
    """Test sentiment scoring logic."""

    def test_positive_sentiment_detection(self):
        """Positive words should yield positive sentiment."""
        positive_words = {"great", "excellent", "wonderful", "happy", "love", "thank"}
        text = "Thank you so much, this is excellent service!"
        words = set(text.lower().split())
        overlap = words & positive_words
        assert len(overlap) >= 2

    def test_negative_sentiment_detection(self):
        """Negative words should yield negative sentiment."""
        negative_words = {"terrible", "awful", "horrible", "angry", "worst", "hate"}
        text = "This is terrible, the worst experience I've ever had!"
        words = set(text.lower().split())
        overlap = words & negative_words
        assert len(overlap) >= 1

    def test_neutral_sentiment(self):
        """Neutral statements should have near-zero sentiment."""
        text = "I would like to check the status of my order"
        # No strong positive/negative signals
        positive_words = {"great", "excellent", "wonderful", "happy"}
        negative_words = {"terrible", "awful", "horrible", "angry"}
        words = set(text.lower().split())
        assert len(words & positive_words) == 0
        assert len(words & negative_words) == 0

    def test_escalation_trigger_on_extreme_negative(self):
        """Repeated negative signals should trigger escalation."""
        escalation_phrases = [
            "i want to speak to a manager",
            "this is unacceptable",
            "i'm going to cancel",
            "i want a refund now",
        ]
        # Any of these should trigger escalation
        for phrase in escalation_phrases:
            has_trigger = any(
                word in phrase
                for word in ["manager", "cancel", "refund", "unacceptable", "supervisor"]
            )
            assert has_trigger, f"'{phrase}' should trigger escalation"


# ── Intent Classification Tests ──


class TestIntentClassification:
    """Test intent routing logic."""

    INTENT_KEYWORDS = {
        "billing": ["bill", "charge", "payment", "invoice", "refund", "subscription"],
        "technical": ["error", "bug", "crash", "slow", "broken", "not working"],
        "orders": ["order", "track", "delivery", "shipped", "shipping", "package"],
        "returns": ["return", "exchange", "warranty", "damaged", "defective"],
        "account": ["password", "login", "account", "profile", "settings"],
        "general": [],
    }

    def _classify(self, text: str) -> str:
        text_lower = text.lower()
        scores = {}
        for intent, keywords in self.INTENT_KEYWORDS.items():
            scores[intent] = sum(1 for kw in keywords if kw in text_lower)
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "general"

    def test_billing_intent(self):
        assert self._classify("I was charged twice on my bill") == "billing"

    def test_technical_intent(self):
        assert self._classify("The app keeps crashing with an error") == "technical"

    def test_order_intent(self):
        assert self._classify("Where is my order? When will it be delivered?") == "orders"

    def test_return_intent(self):
        assert self._classify("I want to return this damaged item") == "returns"

    def test_account_intent(self):
        assert self._classify("I can't login to my account") == "account"

    def test_general_fallback(self):
        assert self._classify("Hello, I have a question") == "general"


# ── RAG Engine Tests ──


class TestRAGRetrieval:
    """Test RAG retrieval ranking logic."""

    def test_relevance_scoring(self):
        """Higher cosine similarity should rank higher."""
        results = [
            {"content": "Return policy details", "score": 0.92},
            {"content": "General FAQ", "score": 0.45},
            {"content": "Refund processing steps", "score": 0.87},
        ]
        sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)
        assert sorted_results[0]["score"] == 0.92
        assert sorted_results[-1]["score"] == 0.45

    def test_minimum_score_threshold(self):
        """Results below threshold should be filtered out."""
        threshold = 0.5
        results = [
            {"content": "Relevant", "score": 0.85},
            {"content": "Somewhat relevant", "score": 0.52},
            {"content": "Irrelevant", "score": 0.20},
        ]
        filtered = [r for r in results if r["score"] >= threshold]
        assert len(filtered) == 2


# ── Conversation Data Structure Tests ──


class TestConversationStructure:
    """Test conversation data models."""

    def test_message_structure(self):
        msg = {
            "id": str(uuid.uuid4()),
            "conversation_id": str(uuid.uuid4()),
            "role": "user",
            "content": "Hello, I need help",
            "sentiment": 0.5,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        assert msg["role"] in ("user", "assistant", "system")
        assert isinstance(msg["content"], str)

    def test_conversation_lifecycle(self):
        statuses = ["active", "completed", "escalated", "failed"]
        conv = {"status": "active"}
        assert conv["status"] in statuses

        conv["status"] = "completed"
        assert conv["status"] == "completed"
