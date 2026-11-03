from fastapi import APIRouter, Depends, Form, UploadFile

from app.features.auth.dependencies import get_current_user
from app.features.speech.base import STTClient
from app.features.speech.provider import get_stt_client
from app.features.speech.schemas import TranscriptionResponse
from app.features.speech.service import transcribe_audio

router = APIRouter(prefix="/speech", tags=["speech"], dependencies=[Depends(get_current_user)])


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(
    audio: UploadFile, language: str = Form("en"), stt_client: STTClient = Depends(get_stt_client)
) -> TranscriptionResponse:
    audio_bytes = await audio.read()
    audio_format = (audio.filename.rsplit(".", 1)[-1] if audio.filename and "." in audio.filename else "wav")
    outcome = transcribe_audio(stt_client, audio_bytes, audio_format, language)
    return TranscriptionResponse(text=outcome.text, confidence=outcome.confidence, needs_repeat=outcome.needs_repeat)
