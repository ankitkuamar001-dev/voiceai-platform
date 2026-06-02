"""Voice Agent API Server — Exposes Webhooks and REST endpoints.

Run:
    uvicorn api:app --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from twilio_webhooks import router as twilio_router
from recording_api import router as recording_router

app = FastAPI(
    title="Voice Agent API",
    description="Twilio webhooks and recording playback API",
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

app.include_router(twilio_router, tags=["twilio"])
app.include_router(recording_router, tags=["recording"])


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "voice-agent-api"}
