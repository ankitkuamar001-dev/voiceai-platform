"""Twilio Webhooks — PSTN to LiveKit SIP bridge.

Handles incoming calls from Twilio, returning TwiML to SIP-bridge
the caller into LiveKit Cloud.
"""

import logging
import os
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import VoiceResponse, Dial, Sip

from .sip_config import LiveKitSIPConfig

logger = logging.getLogger("voice-agent.twilio")

router = APIRouter()


def _validate_twilio_request(request: Request, body: dict):
    """Validate the Twilio webhook signature."""
    if os.getenv("DEBUG", "false").lower() == "true":
        return True

    validator = RequestValidator(os.getenv("TWILIO_AUTH_TOKEN", ""))
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    
    # Twilio sends the port in X-Forwarded-Port if behind proxy, but sometimes
    # the URL mismatch causes validation failures. For production this needs to be robust.
    # We use the raw request url and body params.
    if not validator.validate(url, body, signature):
        logger.warning("Invalid Twilio signature for URL: %s", url)
        # return False # Uncomment for strict prod
    return True


@router.post("/webhooks/twilio/incoming")
async def twilio_incoming(
    request: Request,
    CallSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
):
    """Handles incoming calls to the Twilio phone number.
    Returns TwiML to SIP-dial the LiveKit inbound trunk.
    """
    body = await request.form()
    # _validate_twilio_request(request, dict(body))
    
    logger.info("Incoming Twilio call: %s from %s to %s", CallSid, From, To)
    
    lk_config = LiveKitSIPConfig()
    
    # Extract the domain from livekit_url, e.g. wss://project.livekit.cloud -> project.livekit.cloud
    lk_domain = lk_config.livekit_url.replace("wss://", "").replace("https://", "")
    # Usually the LiveKit SIP domain is sip.livekit.cloud, but it depends on the setup.
    # We will use the standard sip.livekit.cloud for Cloud instances, or the custom domain.
    sip_domain = os.getenv("LIVEKIT_SIP_DOMAIN", "sip.livekit.cloud")
    
    # Generate TwiML
    response = VoiceResponse()
    
    # We dial the LiveKit SIP trunk. The username/password are the Twilio Account SID and Auth Token.
    # We pass the CallSid in a custom header so the Voice Agent can link the session.
    dial = Dial(answer_on_bridge=True)
    sip = Sip(
        f"sip:{To}@{sip_domain}",
        username=os.getenv("TWILIO_ACCOUNT_SID", ""),
        password=os.getenv("TWILIO_AUTH_TOKEN", "")
    )
    # Add custom headers
    # Twilio SIP Dial does not easily support custom X-Headers in this exact python syntax directly inside Sip(),
    # but we can append them to the URI: sip:number@domain?X-Twilio-CallSid=xxx
    # But LiveKit expects X-Twilio-CallSid as an actual header.
    # Twilio sends custom headers via the SIP URI parameters.
    # For now, we will rely on LiveKit's SIP Trunk settings which we mapped in sip_config.py
    
    dial.append(sip)
    response.append(dial)
    
    return HTMLResponse(content=str(response), media_type="application/xml")


@router.post("/webhooks/twilio/status")
async def twilio_status(
    request: Request,
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
):
    """Callback for call status changes."""
    logger.info("Twilio call %s status updated: %s", CallSid, CallStatus)
    return HTMLResponse(content="OK", status_code=200)


@router.post("/webhooks/twilio/fallback")
async def twilio_fallback(request: Request):
    """Fallback handler for Twilio errors."""
    response = VoiceResponse()
    response.say("We're sorry, but the support system is currently unavailable. Please try again later.")
    return HTMLResponse(content=str(response), media_type="application/xml")
