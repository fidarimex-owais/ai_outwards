from dataclasses import dataclass

from app.features.speech.base import STTClient

CONFIDENCE_THRESHOLD = 0.5


@dataclass
class TranscriptionOutcome:
    text: str
    confidence: float
    needs_repeat: bool


def transcribe_audio(client: STTClient, audio_bytes: bytes, audio_format: str = "wav") -> TranscriptionOutcome:
    """Converts audio to text and flags low-confidence results for a repeat prompt,
    per the HLD's Speech-to-Text box ('low confidence -> repeat')."""
    result = client.transcribe(audio_bytes, audio_format)
    # Cloud Whisper models can hallucinate stray punctuation (e.g. ".") on non-speech audio
    # instead of returning an empty string, so "blank" means no alphanumeric content at all.
    has_content = any(ch.isalnum() for ch in result.text)
    needs_repeat = (not has_content) or result.confidence < CONFIDENCE_THRESHOLD
    return TranscriptionOutcome(text=result.text, confidence=result.confidence, needs_repeat=needs_repeat)
