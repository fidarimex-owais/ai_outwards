from pydantic import BaseModel


class TranscriptionResponse(BaseModel):
    text: str
    confidence: float
    needs_repeat: bool
