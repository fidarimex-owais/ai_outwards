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
    def transcribe(self, audio_bytes: bytes, audio_format: str = "wav") -> STTResult:
        """Converts raw audio bytes into text + a confidence score."""
        raise NotImplementedError
