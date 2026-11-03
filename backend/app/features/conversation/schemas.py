from pydantic import BaseModel

from app.features.i18n.translations import DEFAULT_LANGUAGE


class CreateSessionRequest(BaseModel):
    language: str = DEFAULT_LANGUAGE  # "en" | "hi" | "mr"; unrecognized values fall back to en


class AnswerRequest(BaseModel):
    field_key: str
    text: str  # already-transcribed speech (see speech/service.py for the STT step upstream)


class BatchAnswerRequest(BaseModel):
    text: str  # one transcript covering some/all of the remaining fields


class QuestionOut(BaseModel):
    key: str
    label: str
    question: str
    section: str


class TurnResponse(BaseModel):
    session_id: str
    state: str
    language: str = DEFAULT_LANGUAGE
    questions: list[QuestionOut] | None = None       # fields still needing an answer
    clarification_prompt: str | None = None            # set when the last answer needs a retry
    summary: str | None = None                          # set once AWAITING_CONFIRMATION is reached
    next_field_key: str | None = None                    # which field the client should ask/record next
    answered_field_keys: list[str] = []                    # keys already answered (for progress UI)
