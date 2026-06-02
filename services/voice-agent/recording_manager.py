"""Recording Manager — Manages LiveKit Egress recordings.

Provides start/stop recording, S3 upload callbacks, and presigned
URL generation for playback.
"""

import logging
import os
import boto3
from livekit.api import (
    LiveKitAPI,
    RoomCompositeEgressRequest,
    EgressOutput,
    EncodedFileOutput,
)

logger = logging.getLogger("voice-agent.recording")

S3_ENDPOINT = os.getenv("S3_ENDPOINT_URL")
S3_BUCKET = os.getenv("S3_BUCKET", "voiceai-recordings")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")

s3_client = None


def get_s3_client():
    global s3_client
    if s3_client is None:
        s3_client = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION,
        )
    return s3_client


async def start_recording(room_name: str, org_id: str) -> str:
    """Start an audio-only composite egress for a LiveKit room.

    Returns the egress_id.
    """
    if not (LIVEKIT_URL and LIVEKIT_API_KEY and LIVEKIT_API_SECRET):
        logger.warning("LiveKit API credentials missing, skipping recording.")
        return ""

    api = LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    filepath = f"recordings/{org_id}/{room_name}.ogg"

    # Configure S3 upload
    s3_upload = EgressOutput(
        file=EncodedFileOutput(
            filepath=filepath,
            s3=EgressOutput.S3Upload(
                access_key=AWS_ACCESS_KEY_ID,
                secret=AWS_SECRET_ACCESS_KEY,
                region=AWS_REGION,
                bucket=S3_BUCKET,
                endpoint=S3_ENDPOINT,
            ),
        )
    )

    # We want a room composite audio-only recording
    req = RoomCompositeEgressRequest(
        room_name=room_name, audio_only=True, file_outputs=[s3_upload]
    )

    try:
        egress_info = await api.egress.start_room_composite_egress(req)
        logger.info(
            "Started recording for room %s (egress_id: %s)",
            room_name,
            egress_info.egress_id,
        )
        return egress_info.egress_id
    except Exception as exc:
        logger.error("Failed to start recording for room %s: %s", room_name, exc)
        return ""
    finally:
        await api.aclose()


async def stop_recording(egress_id: str) -> None:
    """Stop an active LiveKit egress recording."""
    if not egress_id:
        return

    api = LiveKitAPI(LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
    try:
        await api.egress.stop_egress(egress_id)
        logger.info("Stopped recording (egress_id: %s)", egress_id)
    except Exception as exc:
        logger.error("Failed to stop recording %s: %s", egress_id, exc)
    finally:
        await api.aclose()


def get_playback_url(object_key: str, expires_in: int = 900) -> str:
    """Generate a pre-signed S3 URL for recording playback."""
    try:
        client = get_s3_client()
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": object_key},
            ExpiresIn=expires_in,
        )
        return url
    except Exception as exc:
        logger.error("Failed to generate presigned URL for %s: %s", object_key, exc)
        return ""
