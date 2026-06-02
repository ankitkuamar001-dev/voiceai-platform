"""SIP / Twilio Configuration for the Voice Agent.

Manages:
  • Twilio SIP trunk credentials
  • LiveKit SIP inbound trunk & dispatch rules
  • Phone number → room routing
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("voice-agent.sip")


# ── Configuration ──


@dataclass(frozen=True)
class TwilioConfig:
    """Twilio account credentials loaded from environment."""

    account_sid: str = field(
        default_factory=lambda: os.getenv("TWILIO_ACCOUNT_SID", "")
    )
    auth_token: str = field(default_factory=lambda: os.getenv("TWILIO_AUTH_TOKEN", ""))
    sip_domain: str = field(default_factory=lambda: os.getenv("TWILIO_SIP_DOMAIN", ""))
    phone_number: str = field(
        default_factory=lambda: os.getenv("TWILIO_PHONE_NUMBER", "")
    )

    @property
    def is_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token)


@dataclass(frozen=True)
class LiveKitSIPConfig:
    """LiveKit SIP integration settings."""

    livekit_url: str = field(default_factory=lambda: os.getenv("LIVEKIT_URL", ""))
    livekit_api_key: str = field(
        default_factory=lambda: os.getenv("LIVEKIT_API_KEY", "")
    )
    livekit_api_secret: str = field(
        default_factory=lambda: os.getenv("LIVEKIT_API_SECRET", "")
    )
    sip_trunk_id: str = field(
        default_factory=lambda: os.getenv("LIVEKIT_SIP_TRUNK_ID", "")
    )

    @property
    def is_configured(self) -> bool:
        return bool(
            self.livekit_url and self.livekit_api_key and self.livekit_api_secret
        )


# ── SIP Trunk Setup ──


def get_sip_trunk_config(twilio: TwilioConfig) -> dict[str, Any]:
    """Generate the LiveKit SIP Inbound Trunk configuration.

    This JSON is used to register a SIP trunk with LiveKit Cloud
    via ``POST /sip/trunk/inbound``.
    """
    return {
        "trunk": {
            "name": "voiceai-twilio-trunk",
            "numbers": [twilio.phone_number] if twilio.phone_number else [],
            "auth_username": twilio.account_sid,
            "auth_password": twilio.auth_token,
            "headers": {
                "X-VoiceAI-Source": "twilio",
            },
            "headers_to_attributes": {
                "X-Twilio-CallSid": "twilio.call_sid",
                "X-Twilio-Caller": "twilio.caller",
                "X-Twilio-Called": "twilio.called",
            },
        },
    }


def get_dispatch_rules(lk_config: LiveKitSIPConfig) -> dict[str, Any]:
    """Generate SIP Dispatch Rule configuration.

    Dispatch rules tell LiveKit how to route inbound SIP calls to rooms.
    Rule: every call creates a new room named ``call-<call_sid>`` and
    dispatches the ``entrypoint`` agent defined in voice_agent.py.
    """
    return {
        "rules": [
            {
                "name": "voiceai-default-dispatch",
                "trunk_ids": [lk_config.sip_trunk_id] if lk_config.sip_trunk_id else [],
                "rule": {
                    "dispatchRuleIndividual": {
                        "roomPrefix": "call-",
                    },
                },
                "attributes": {
                    "agent.type": "voice-support",
                    "agent.version": "1.0",
                },
            },
        ],
    }


# ── Phone Number Routing ──


ROUTING_TABLE: dict[str, dict[str, str]] = {
    # Map inbound phone numbers to specific org + language configs
    # "+18001234567": {"org_id": "uuid-here", "language": "en-US"},
    # "+18001234568": {"org_id": "uuid-here", "language": "es-MX"},
}


def route_call(called_number: str) -> dict[str, str]:
    """Look up routing config for an inbound phone number.

    Returns a dict with ``org_id``, ``language``, and any other metadata
    that should be injected into the LiveKit room as attributes.
    """
    route = ROUTING_TABLE.get(called_number)
    if route:
        logger.info(
            "Routing call to %s → org %s (%s)",
            called_number,
            route["org_id"],
            route["language"],
        )
        return route

    # Default routing
    logger.warning("No explicit route for %s — using default org", called_number)
    return {
        "org_id": os.getenv("DEFAULT_ORG_ID", "00000000-0000-0000-0000-000000000000"),
        "language": "en-US",
    }


# ── Utility: Register Trunk via LiveKit API ──


async def register_sip_trunk() -> dict[str, Any] | None:
    """Register the SIP trunk with LiveKit Cloud (idempotent).

    Requires ``httpx`` and valid LiveKit + Twilio credentials.
    Returns the created/existing trunk metadata, or None on failure.
    """
    twilio = TwilioConfig()
    lk = LiveKitSIPConfig()

    if not twilio.is_configured:
        logger.warning("Twilio not configured — skipping SIP trunk registration")
        return None
    if not lk.is_configured:
        logger.warning("LiveKit not configured — skipping SIP trunk registration")
        return None

    import httpx

    trunk_payload = get_sip_trunk_config(twilio)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{lk.livekit_url}/sip/trunk/inbound",
                json=trunk_payload,
                headers={
                    "Authorization": f"Bearer {lk.livekit_api_key}:{lk.livekit_api_secret}",
                },
            )
            resp.raise_for_status()
            result = resp.json()
            logger.info(
                "SIP trunk registered: %s", result.get("trunk", {}).get("sip_trunk_id")
            )
            return result
    except Exception as exc:
        logger.error("Failed to register SIP trunk: %s", exc)
        return None


# ── Self-test ──

if __name__ == "__main__":
    import json

    twilio = TwilioConfig()
    lk = LiveKitSIPConfig()

    print("Twilio configured:", twilio.is_configured)
    print("LiveKit configured:", lk.is_configured)
    print()
    print("SIP Trunk Config:")
    print(json.dumps(get_sip_trunk_config(twilio), indent=2))
    print()
    print("Dispatch Rules:")
    print(json.dumps(get_dispatch_rules(lk), indent=2))
    print()
    print("Route +18001234567:", route_call("+18001234567"))
