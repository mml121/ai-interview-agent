import json

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.auth import require_candidate
from app.core.config import get_settings
from app.models.auth import CandidateAccessToken

router = APIRouter(prefix="/api/voice", tags=["voice"])

MAX_AUDIO_BYTES = 12 * 1024 * 1024
MAX_SPEECH_TEXT_CHARS = 4000


class SpeechRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_SPEECH_TEXT_CHARS)


def elevenlabs_base_url() -> str:
    settings = get_settings()
    if not settings.elevenlabs_api_key:
        raise HTTPException(
            status_code=503,
            detail="Voice mode requires ELEVENLABS_API_KEY in backend/.env",
        )
    return settings.elevenlabs_api_url.rstrip("/")


def provider_error_detail(action: str, response: httpx.Response) -> str:
    if response.status_code in {401, 403}:
        return f"{action} failed because the voice service rejected the configured API key"
    if response.status_code == 429:
        return f"{action} failed because the voice service rate limit was reached"
    return f"{action} failed with status {response.status_code}"


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    access_token: CandidateAccessToken = Depends(require_candidate),
):
    del access_token
    settings = get_settings()
    base_url = elevenlabs_base_url()
    audio = await file.read()

    if not audio:
        raise HTTPException(status_code=400, detail="No audio was recorded")

    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Recorded audio is too large")

    headers = {"xi-api-key": settings.elevenlabs_api_key or ""}
    files = {
        "file": (
            file.filename or "answer.webm",
            audio,
            file.content_type or "audio/webm",
        )
    }
    data = {
        "model_id": settings.elevenlabs_stt_model,
        "language_code": "en",
        "tag_audio_events": "false",
        "diarize": "false",
    }

    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(
                f"{base_url}/speech-to-text",
                headers=headers,
                files=files,
                data=data,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=provider_error_detail("Transcription", exc.response),
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Transcription service is unreachable") from exc

    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="Transcription service returned invalid JSON") from exc
    transcript = str(payload.get("text") or "").strip()

    if not transcript:
        raise HTTPException(status_code=400, detail="No speech was detected in the recording")

    return {"text": transcript}


@router.post("/speech")
async def synthesize_speech(
    request: SpeechRequest,
    access_token: CandidateAccessToken = Depends(require_candidate),
):
    del access_token
    settings = get_settings()
    base_url = elevenlabs_base_url()
    text = request.text.strip()

    if not text:
        raise HTTPException(status_code=400, detail="Speech text is required")

    payload = {
        "text": text,
        "model_id": settings.elevenlabs_tts_model,
        "voice_settings": {
            "stability": 0.42,
            "similarity_boost": 0.78,
            "style": 0.24,
            "use_speaker_boost": True,
        },
    }
    headers = {
        "xi-api-key": settings.elevenlabs_api_key or "",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(
                f"{base_url}/text-to-speech/{settings.elevenlabs_voice_id}?output_format=mp3_44100_128",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=provider_error_detail("Speech generation", exc.response),
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Speech service is unreachable") from exc

    return Response(content=response.content, media_type="audio/mpeg")
