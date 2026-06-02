"""Escalation Engine — Multi-signal logic for human handoff."""

import logging
from dataclasses import dataclass
from typing import List

logger = logging.getLogger("voice-agent.escalation")


@dataclass
class EscalationDecision:
    should_escalate: bool
    reason: str
    urgency: int
    signals: List[str]


class EscalationEngine:
    def __init__(self, org_id: str):
        self.org_id = org_id
        # In a real system, these thresholds would be loaded from DB/Redis per org
        self.sentiment_threshold = -0.5
        self.max_turns = 20
        self.trigger_keywords = [
            "manager",
            "supervisor",
            "lawyer",
            "sue",
            "complaint",
            "human",
        ]

    def evaluate(
        self,
        turn_count: int,
        sentiment_scores: List[float],
        intent_history: List[str],
        latest_user_utterance: str,
        customer_tier: str = "standard",
    ) -> EscalationDecision:
        """Evaluate whether a conversation should be escalated."""
        signals = []
        urgency = 3

        # 1. Turn count limit
        if turn_count > self.max_turns:
            signals.append("max_turns_exceeded")

        # 2. Sentiment trend
        if len(sentiment_scores) >= 3:
            recent_avg = sum(sentiment_scores[-3:]) / 3
            if recent_avg <= self.sentiment_threshold:
                signals.append("negative_sentiment_trend")

        # 3. Trigger keywords
        lower_utterance = latest_user_utterance.lower()
        for kw in self.trigger_keywords:
            if kw in lower_utterance:
                signals.append(f"keyword_match:{kw}")
                urgency = 4

        # 4. Repeated intents
        if len(intent_history) >= 3:
            if intent_history[-1] == intent_history[-2] == intent_history[-3]:
                if intent_history[-1] not in ["greeting", "acknowledgement", "unknown"]:
                    signals.append("repeated_intent")

        # 5. VIP tier escalation threshold relaxation (mock logic)
        if customer_tier == "enterprise" and len(signals) == 0 and turn_count > 10:
            signals.append("vip_proactive_escalation")

        should_escalate = len(signals) > 0
        reason = ", ".join(signals) if should_escalate else ""

        return EscalationDecision(
            should_escalate=should_escalate,
            reason=reason,
            urgency=urgency,
            signals=signals,
        )
