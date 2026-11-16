from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile

from app.features.auth.dependencies import get_current_user
from app.features.speech.base import STTClient
from app.features.speech.provider import get_stt_client
from app.features.speech.schemas import TranscriptionResponse
from app.features.speech.service import transcribe_audio

router = APIRouter(prefix="/speech", tags=["speech"], dependencies=[Depends(get_current_user)])

# Caps how large an audio upload this endpoint accepts. 10 MB comfortably covers a realistic
# 1-2 minute browser recording (well under 2 MB at typical MediaRecorder bitrates) with a lot
# of headroom, while staying under Groq's own 25 MB free-tier transcription limit.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_UPLOAD_READ_CHUNK_SIZE = 1024 * 1024


@router.post("/transcribe", response_model=TranscriptionResponse)
def transcribe(
    request: Request, audio: UploadFile, language: str = Form("en"), stt_client: STTClient = Depends(get_stt_client)
) -> TranscriptionResponse:
    # Plain `def`, not `async def`: transcribe_audio() below makes a blocking network call
    # (Groq) or runs blocking CPU inference (local Whisper). A sync route is dispatched to
    # FastAPI's threadpool, matching every other router in this app; an async route would run
    # this directly on the event loop and block all concurrent requests for its duration.

    # Content-Length check: cheap and immediate when an honest client declares it, but not a
    # substitute for the chunked read below - a client can omit or lie about this header, and
    # by the time this route body runs, FastAPI has already parsed the multipart upload into
    # `audio` to resolve this very parameter, so this check does not avoid that parsing cost.
    content_length = request.headers.get("content-length")
    if content_length is not None and content_length.isdigit() and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Audio file too large")

    # Reads in capped chunks instead of audio.file.read() in one call, so an oversized upload
    # is rejected after at most MAX_UPLOAD_BYTES + one chunk have been read by this loop -
    # audio_bytes (the full joined buffer) is never built for a file over the cap.
    chunks: list[bytes] = []
    total_read = 0
    while True:
        chunk = audio.file.read(_UPLOAD_READ_CHUNK_SIZE)
        if not chunk:
            break
        total_read += len(chunk)
        if total_read > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Audio file too large")
        chunks.append(chunk)
    audio_bytes = b"".join(chunks)

    audio_format = (audio.filename.rsplit(".", 1)[-1] if audio.filename and "." in audio.filename else "wav")
    outcome = transcribe_audio(stt_client, audio_bytes, audio_format, language)
    return TranscriptionResponse(text=outcome.text, confidence=outcome.confidence, needs_repeat=outcome.needs_repeat)
