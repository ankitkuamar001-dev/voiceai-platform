"""WhatsApp Service — Twilio WhatsApp integration.

Manages incoming WhatsApp messages via Twilio Webhooks, maintains 24-hour
sessions, and integrates with the AI Brain for response generation.
"""

import os
import sys
import logging
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from twilio.rest import Client
from sqlalchemy import text

sys.path.insert(0, "/app")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from shared.utils.database import async_session_factory

logger = logging.getLogger("whatsapp-service")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="WhatsApp Service",
    description="Twilio WhatsApp API integration for voice-agent platform",
    version="1.0.0",
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

# ── Config ──
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "")
AI_BRAIN_URL = os.getenv("AI_BRAIN_URL", "http://localhost:8001")
DEFAULT_ORG_ID = os.getenv("DEFAULT_ORG_ID", "00000000-0000-0000-0000-000000000000")

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID else None

# ── Schemas ──

class SendMessageRequest(BaseModel):
    to_number: str
    body: str

# ── Helpers ──

async def get_or_create_conversation(phone_number: str, org_id: str) -> str:
    """Finds an active WhatsApp conversation for the phone number or creates one."""
    async with async_session_factory() as session:
        # Check for active conversation within 24 hours
        result = await session.execute(
            text("""
                SELECT id, updated_at
                FROM conversations
                WHERE whatsapp_phone = :phone
                  AND org_id = :org_id
                  AND channel = 'whatsapp'
                  AND status IN ('initiated', 'in_progress')
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"phone": phone_number, "org_id": org_id}
        )
        row = result.mappings().one_or_none()
        
        if row:
            # Check 24-hour window
            if row["updated_at"].replace(tzinfo=timezone.utc) > datetime.now(timezone.utc) - timedelta(hours=24):
                return str(row["id"])
                
        # Create new conversation
        result = await session.execute(
            text("""
                INSERT INTO conversations (org_id, channel, direction, status, whatsapp_phone)
                VALUES (:org_id, 'whatsapp', 'inbound', 'in_progress', :phone)
                RETURNING id
            """),
            {"org_id": org_id, "phone": phone_number}
        )
        await session.commit()
        return str(result.mappings().one()["id"])

async def handle_ai_response(conversation_id: str, message: str, phone_number: str):
    """Sends the message to the AI Brain and replies via Twilio."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. Ask AI Brain for response
            resp = await client.post(
                f"{AI_BRAIN_URL}/api/v1/ai/chat",
                json={
                    "messages": [{"role": "user", "content": message}],
                    "conversation_id": conversation_id,
                    "org_id": DEFAULT_ORG_ID,
                }
            )
            resp.raise_for_status()
            ai_data = resp.json()
            reply_text = ai_data.get("response", "I'm sorry, I encountered an error.")
            
            # 2. Log user message to DB
            await client.post(
                f"{AI_BRAIN_URL}/api/v1/conversations/{conversation_id}/messages",
                json={
                    "content": message,
                    "sender_type": "customer",
                    "org_id": DEFAULT_ORG_ID,
                }
            )
            
            # 3. Log AI response to DB
            await client.post(
                f"{AI_BRAIN_URL}/api/v1/conversations/{conversation_id}/messages",
                json={
                    "content": reply_text,
                    "sender_type": "ai_bot",
                    "org_id": DEFAULT_ORG_ID,
                }
            )
            
            # 4. Send Twilio WhatsApp Reply
            if twilio_client:
                twilio_client.messages.create(
                    body=reply_text,
                    from_=TWILIO_WHATSAPP_NUMBER,
                    to=phone_number
                )
            else:
                logger.warning("Twilio client not configured, skipping WhatsApp send.")
                
    except Exception as exc:
        logger.error("Error in AI pipeline: %s", exc)

# ── Routes ──

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "whatsapp-service"}

@app.post("/webhooks/whatsapp/incoming")
async def whatsapp_incoming(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...)
):
    """Handles incoming WhatsApp messages from Twilio."""
    # Note: Signature validation skipped for brevity, similar to Twilio Voice
    logger.info("Incoming WhatsApp from %s: %s", From, Body)
    
    # Run conversation logic in background task to avoid blocking webhook response
    # (Twilio expects a 200 OK or TwiML within 15 seconds)
    import asyncio
    
    async def background_task():
        conv_id = await get_or_create_conversation(From, DEFAULT_ORG_ID)
        await handle_ai_response(conv_id, Body, From)
        
    asyncio.create_task(background_task())
    
    # Return empty TwiML (200 OK)
    return HTMLResponse(content="<Response></Response>", media_type="application/xml")

@app.post("/api/v1/whatsapp/send")
async def send_whatsapp(req: SendMessageRequest):
    """API for sending outbound WhatsApp messages."""
    if not twilio_client:
        raise HTTPException(status_code=500, detail="Twilio client not configured")
        
    try:
        message = twilio_client.messages.create(
            body=req.body,
            from_=TWILIO_WHATSAPP_NUMBER,
            to=req.to_number
        )
        return {"status": "sent", "message_sid": message.sid}
    except Exception as exc:
        logger.error("Failed to send WhatsApp message: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to send message")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8006, reload=True)
