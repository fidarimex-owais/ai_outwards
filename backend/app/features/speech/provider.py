import math
import os
import tempfile

from faster_whisper import WhisperModel

from app.features.speech.base import STTClient, STTResult


class LocalWhisperSTTClient(STTClient):
    """STT provider backed by a locally-run faster-whisper model. No API key, no per-request
    cost, no network call — fits the MSI goal of minimizing operational cost. The model is
    loaded lazily on first use, not at construction time, so creating this client is cheap."""

    def __init__(
        self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8", cpu_threads: int = 8
    ):
        self._model_size = model_size
        self._device = device
        self._compute_type = compute_type
        # faster-whisper/CTranslate2 defaults to a conservative thread count on CPU; giving
        # it more of the machine's cores (without claiming all of them - the API server,
        # Mongo, Redis, and your browser are also running) is a real speedup for CPU
        # inference, separate from the beam_size/vad_filter changes in transcribe() below.
        self._cpu_threads = cpu_threads
        self._model: WhisperModel | None = None

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            self._model = WhisperModel(
                self._model_size, device=self._device, compute_type=self._compute_type,
                cpu_threads=self._cpu_threads,
            )
        return self._model

    def transcribe(self, audio_bytes: bytes, audio_format: str = "wav") -> STTResult:
        model = self._get_model()

        with tempfile.NamedTemporaryFile(suffix=f".{audio_format}", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            # beam_size=1 (greedy decoding) instead of faster-whisper's default of 5, and
            # vad_filter=True to skip silent stretches (e.g. pauses between answers when
            # recording all 16 questions in one take) - both are standard CPU speed
            # optimizations; for this kind of short, structured speech the accuracy cost is
            # minimal while the time saved is real, since beam search width is the main cost
            # driver on CPU, not model size.
            segments, _info = model.transcribe(tmp_path, beam_size=1, vad_filter=True)
            segments = list(segments)
        finally:
            os.remove(tmp_path)

        text = " ".join(seg.text.strip() for seg in segments).strip()
        confidence = self._estimate_confidence(segments)
        return STTResult(text=text, confidence=confidence)

    @staticmethod
    def _estimate_confidence(segments) -> float:
        """faster-whisper doesn't return a direct confidence score either. Same approach as
        before: approximate from each segment's avg_logprob (log-probability -> probability
        via exp), averaged across segments. Falls back to 1.0 if no segment data."""
        if not segments:
            return 1.0

        probs = [math.exp(seg.avg_logprob) for seg in segments if seg.avg_logprob is not None]
        if not probs:
            return 1.0

        return max(0.0, min(1.0, sum(probs) / len(probs)))


_default_client: STTClient | None = None


def get_stt_client() -> STTClient:
    """FastAPI dependency: a single shared client so the (lazily-loaded) model is only
    loaded once per process, not once per request."""
    global _default_client
    if _default_client is None:
        _default_client = LocalWhisperSTTClient()
    return _default_client
