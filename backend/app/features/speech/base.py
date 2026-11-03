from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class STTResult:
    text: str
    confidence: float  # 0.0–1.0


class STTClient(ABC):
    """Interface every speech-to-text provider must implement, so the provider can be swapped
    (Whisper, Deepgram, Google STT, local model) without touching any caller."""

    @abstractmethod
    def transcribe(self, audio_bytes: bytes, audio_format: str = "wav", language: str = "en") -> STTResult:
        """Converts raw audio bytes into text + a confidence score. `language` is an ISO-639-1
        hint ("en"/"hi"/"mr") for the conversation's selected language - not a guarantee the
        speaker only used that language (code-switching is expected and handled downstream by
        the LLM extraction step, not here)."""
        raise NotImplementedError
