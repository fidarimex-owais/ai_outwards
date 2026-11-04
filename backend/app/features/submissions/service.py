from datetime import datetime, timezone

import redis
from pymongo.database import Database

from app.core.exceptions import ExtractionParseFailed
from app.features.conversation.fields import FIELD_DEFINITIONS, get_field
from app.features.conversation.repository import load_session, save_session
from app.features.conversation.schemas import TurnResponse
from app.features.conversation.state_machine import transition
from app.features.conversation.states import SessionState
from app.features.extraction.router_msi import extract_correction
from app.features.extraction.schemas import FieldType
from app.features.guardrails.input_guard import check_input
from app.features.i18n.translations import normalize_language, ui_text
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


def _validate_value(field_def, raw_value, language: str):
    if field_def.field_type == FieldType.TEXT:
        return validate_text(
            raw_value, field_def.localized_label(language), language,
            required=field_def.required, allowed_values=field_def.allowed_values,
        )
    if field_def.field_type == FieldType.NUMBER:
        return validate_number(raw_value, field_def.localized_label(language), language, min_value=0)
    if field_def.field_type == FieldType.VEHICLE_NUMBER:
        return validate_vehicle_number(raw_value, field_def.localized_label(language), language)
    if field_def.field_type == FieldType.TIME:
        return validate_time(raw_value, field_def.localized_label(language), language)
    raise ValueError(f"Unknown field type: {field_def.field_type}")


def _total(answers: dict) -> int:
    return calculate_total(
        answers["four_hand"], answers["five_hand"], answers["six_hand"], answers["eight_hand"], answers["cluster"]
    )


def _with_total(answers: dict) -> dict:
    fields = dict(answers)
    fields["total"] = _total(answers)
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
            # English-normalized values only - the conversation language never reaches
            # storage, per the "English-only database" requirement.
            **_with_total(session["answers"]),
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            insert_submission(self._db, submission)  # idempotent - duplicate save is a no-op, not an error
        except Exception:
            # Anything other than the idempotent-duplicate case (already handled inside
            # insert_submission): fall back to AWAITING_CONFIRMATION so the client can retry
            # /confirm instead of being stuck in SAVING forever (SAVING has no "confirm" event).
            session["state"] = transition(SessionState.SAVING, "save_failure").value
            save_session(self._redis, session)
            raise

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
        language = normalize_language(session.get("language"))

        # 'correct' is only a defined transition from AWAITING_CONFIRMATION - this naturally
        # rejects corrections attempted from any other state (e.g. after SAVING/COMPLETED).
        session["state"] = transition(current_state, "correct").value

        guard = check_input(raw_text)
        if not guard.allowed:
            save_session(self._redis, session)
            return TurnResponse(
                session_id=session_id, state=session["state"], language=language,
                clarification_prompt=ui_text("sorry_try_again", language),
            )

        fields = [
            (f.key, f.label, f.field_type, session["answers"].get(f.key), f.proper_noun, f.allowed_values)
            for f in FIELD_DEFINITIONS
        ]
        # Note: unlike conversation/service.py's submit_answer, AllLLMsFailed is NOT caught
        # here - AWAITING_CONFIRMATION has no llm_failure transition (only COLLECTING and
        # CLARIFICATION pause on LLM failure). It propagates to the 503 error handler and the
        # session simply stays in AWAITING_CONFIRMATION, ready to retry the correction.
        try:
            correction = extract_correction(fields, raw_text, self._llm_chain, session_id, language)
        except ExtractionParseFailed:
            # The LLM responded but not with valid JSON - ask the user to just retry the
            # correction, not a provider outage (that's AllLLMsFailed, left to propagate above).
            save_session(self._redis, session)
            return TurnResponse(
                session_id=session_id, state=session["state"], language=language,
                clarification_prompt=ui_text("sorry_try_again", language),
            )

        if correction.field_key is None:
            save_session(self._redis, session)
            return TurnResponse(
                session_id=session_id, state=session["state"], language=language,
                clarification_prompt=ui_text("could_not_tell_field", language),
            )

        field_def = get_field(correction.field_key)
        question = field_def.localized_question(language)

        if correction.value in (None, "") and not field_def.required:
            session["answers"][field_def.key] = ""
            session["display_answers"][field_def.key] = ""
            save_session(self._redis, session)
            return self._summary_response(session)

        if correction.ambiguous or correction.value is None:
            save_session(self._redis, session)
            return TurnResponse(
                session_id=session_id, state=session["state"], language=language,
                clarification_prompt=ui_text("new_value_unclear", language, question=question),
            )

        validation = _validate_value(field_def, correction.value, language)
        if not validation.valid:
            save_session(self._redis, session)
            return TurnResponse(
                session_id=session_id, state=session["state"], language=language,
                clarification_prompt=f"{validation.error}. {question}",
            )

        session["answers"][field_def.key] = validation.value
        session["display_answers"][field_def.key] = correction.display_value
        save_session(self._redis, session)
        return self._summary_response(session)

    def _summary_response(self, session: dict) -> TurnResponse:
        language = normalize_language(session.get("language"))
        display_fields = dict(session["display_answers"])
        display_fields["total"] = _total(session["answers"])
        return TurnResponse(
            session_id=session["session_id"],
            state=session["state"],
            language=language,
            summary=build_summary(display_fields, language),
        )
