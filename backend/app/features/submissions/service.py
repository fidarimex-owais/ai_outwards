from datetime import datetime, timezone

import redis
from pymongo.database import Database

from app.features.conversation.fields import get_field
from app.features.conversation.repository import load_session, save_session
from app.features.conversation.schemas import TurnResponse
from app.features.conversation.state_machine import transition
from app.features.conversation.states import SessionState
from app.features.extraction.router_msi import extract_field
from app.features.extraction.schemas import FieldType
from app.features.guardrails.input_guard import check_input
from app.features.llm.chain import LLMChain
from app.features.submissions.repository import insert_submission
from app.features.submissions.schemas import SubmissionOut
from app.features.summary.builder import build_summary
from app.features.validation.calculator import calculate_total
from app.features.validation.validators import (
    validate_number,
    validate_text,
    validate_time,
    validate_vehicle_number,
)


def _validate_value(field_def, raw_value):
    if field_def.field_type == FieldType.TEXT:
        return validate_text(raw_value, field_def.label, required=field_def.required)
    if field_def.field_type == FieldType.NUMBER:
        return validate_number(raw_value, field_def.label, min_value=0)
    if field_def.field_type == FieldType.VEHICLE_NUMBER:
        return validate_vehicle_number(raw_value, field_def.label)
    if field_def.field_type == FieldType.TIME:
        return validate_time(raw_value, field_def.label)
    raise ValueError(f"Unknown field type: {field_def.field_type}")


def _with_total(answers: dict) -> dict:
    fields = dict(answers)
    fields["total"] = calculate_total(
        fields["four_hand"], fields["five_hand"], fields["six_hand"], fields["eight_hand"], fields["cluster"]
    )
    return fields


class SubmissionService:
    def __init__(self, redis_client: redis.Redis, db: Database, llm_chain: LLMChain):
        self._redis = redis_client
        self._db = db
        self._llm_chain = llm_chain

    def confirm(self, session_id: str) -> SubmissionOut:
        session = load_session(self._redis, session_id)
        current_state = SessionState(session["state"])

        session["state"] = transition(current_state, "confirm").value  # AWAITING_CONFIRMATION -> SAVING
        save_session(self._redis, session)

        submission = {
            "session_id": session_id,
            **_with_total(session["answers"]),
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        insert_submission(self._db, submission)  # idempotent - duplicate save is a no-op, not an error

        session["state"] = transition(SessionState.SAVING, "save_success").value
        save_session(self._redis, session)
        # Session is kept in Redis (marked COMPLETED), not deleted, so a repeated GET still
        # reports COMPLETED. Natural TTL expiry cleans it up eventually.

        return SubmissionOut(**submission)

    def correct_field(self, session_id: str, field_key: str, raw_text: str) -> TurnResponse:
        session = load_session(self._redis, session_id)
        current_state = SessionState(session["state"])

        # 'correct' is only a defined transition from AWAITING_CONFIRMATION - this naturally
        # rejects corrections attempted from any other state (e.g. after SAVING/COMPLETED).
        session["state"] = transition(current_state, "correct").value

        field_def = get_field(field_key)

        if not raw_text.strip() and not field_def.required:
            session["answers"][field_key] = ""
            save_session(self._redis, session)
            return self._summary_response(session)

        guard = check_input(raw_text)
        if not guard.allowed:
            save_session(self._redis, session)
            return TurnResponse(
                session_id=session_id, state=session["state"],
                clarification_prompt=f"Sorry, I didn't catch that. {field_def.question}",
            )

        # Note: unlike conversation/service.py's submit_answer, AllLLMsFailed is NOT caught
        # here - AWAITING_CONFIRMATION has no llm_failure transition (only COLLECTING and
        # CLARIFICATION pause on LLM failure). It propagates to the 503 error handler and the
        # session simply stays in AWAITING_CONFIRMATION, ready to retry the correction.
        extracted = extract_field(field_def.field_type, field_def.label, raw_text, self._llm_chain, session_id)

        if extracted.ambiguous or extracted.value is None:
            save_session(self._redis, session)
            return TurnResponse(
                session_id=session_id, state=session["state"],
                clarification_prompt=f"I couldn't understand that clearly. {field_def.question}",
            )

        validation = _validate_value(field_def, extracted.value)
        if not validation.valid:
            save_session(self._redis, session)
            return TurnResponse(
                session_id=session_id, state=session["state"],
                clarification_prompt=f"{validation.error}. {field_def.question}",
            )

        session["answers"][field_key] = validation.value
        save_session(self._redis, session)
        return self._summary_response(session)

    def _summary_response(self, session: dict) -> TurnResponse:
        return TurnResponse(
            session_id=session["session_id"],
            state=session["state"],
            summary=build_summary(_with_total(session["answers"])),
        )
