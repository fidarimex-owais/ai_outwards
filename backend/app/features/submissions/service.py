from datetime import datetime, timezone

import redis
from pymongo.database import Database

from app.features.conversation.fields import FIELD_DEFINITIONS, get_field
from app.features.conversation.repository import load_session, save_session
from app.features.conversation.schemas import TurnResponse
from app.features.conversation.state_machine import transition
from app.features.conversation.states import SessionState
from app.features.extraction.router_msi import extract_correction
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

    def correct_field(self, session_id: str, raw_text: str) -> TurnResponse:
        """Takes one free-form spoken correction (e.g. "Correct the labor name to Sagar
        Panidrahi", or just "change Sagar to Sagar Panidrahi") and figures out which field it
        refers to - the speaker names the field or its current value in their own words, never
        a machine key, so which field is being corrected is itself something to extract, not
        something the caller already knows."""
        session = load_session(self._redis, session_id)
        current_state = SessionState(session["state"])

        # 'correct' is only a defined transition from AWAITING_CONFIRMATION - this naturally
        # rejects corrections attempted from any other state (e.g. after SAVING/COMPLETED).
        session["state"] = transition(current_state, "correct").value

        guard = check_input(raw_text)
        if not guard.allowed:
            save_session(self._redis, session)
            return TurnResponse(
                session_id=session_id, state=session["state"],
                clarification_prompt="Sorry, I didn't catch that. Which field would you like to correct, and to what?",
            )

        fields = [
            (f.key, f.label, f.field_type, session["answers"].get(f.key))
            for f in FIELD_DEFINITIONS
        ]
        # Note: unlike conversation/service.py's submit_answer, AllLLMsFailed is NOT caught
        # here - AWAITING_CONFIRMATION has no llm_failure transition (only COLLECTING and
        # CLARIFICATION pause on LLM failure). It propagates to the 503 error handler and the
        # session simply stays in AWAITING_CONFIRMATION, ready to retry the correction.
        correction = extract_correction(fields, raw_text, self._llm_chain, session_id)

        if correction.field_key is None:
            save_session(self._redis, session)
            return TurnResponse(
                session_id=session_id, state=session["state"],
                clarification_prompt="I couldn't tell which field you meant. Please say which field to correct and its new value.",
            )

        field_def = get_field(correction.field_key)

        if correction.value in (None, "") and not field_def.required:
            session["answers"][field_def.key] = ""
            save_session(self._redis, session)
            return self._summary_response(session)

        if correction.ambiguous or correction.value is None:
            save_session(self._redis, session)
            return TurnResponse(
                session_id=session_id, state=session["state"],
                clarification_prompt=f"I couldn't understand the new value clearly. {field_def.question}",
            )

        validation = _validate_value(field_def, correction.value)
        if not validation.valid:
            save_session(self._redis, session)
            return TurnResponse(
                session_id=session_id, state=session["state"],
                clarification_prompt=f"{validation.error}. {field_def.question}",
            )

        session["answers"][field_def.key] = validation.value
        save_session(self._redis, session)
        return self._summary_response(session)

    def _summary_response(self, session: dict) -> TurnResponse:
        return TurnResponse(
            session_id=session["session_id"],
            state=session["state"],
            summary=build_summary(_with_total(session["answers"])),
        )
