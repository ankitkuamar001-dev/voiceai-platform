"""Recording API — FastAPI routes for accessing call recordings."""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from recording_manager import get_playback_url

logger = logging.getLogger("voice-agent.recording.api")

router = APIRouter()

# Typically these endpoints would query the database for the call_recordings table.
# Since we are in the voice-agent, we will do a proxy call to analytics or ticket service,
# or we can do raw DB calls here. However, to keep it clean, we just return the URL directly.

class PlaybackResponse(BaseModel):
    url: str
    expires_in: int

@router.get("/api/v1/recordings/{recording_id}/playback", response_model=PlaybackResponse)
async def get_recording_playback(recording_id: str, org_id: str):
    """Get a presigned S3 playback URL for a recording."""
    # Note: In a real system we would look up the S3 object key via the DB using recording_id.
    # For now, we assume the object key is structured deterministically or passed directly.
    # We will assume recording_id is actually the room_name or conversation_id.
    
    object_key = f"recordings/{org_id}/call-{recording_id}.ogg"
    
    url = get_playback_url(object_key, expires_in=900)
    if not url:
        raise HTTPException(status_code=404, detail="Recording not found or unavailable")
        
    return PlaybackResponse(url=url, expires_in=900)
