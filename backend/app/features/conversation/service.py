import redis

from app.core.exceptions import AllLLMsFailed, InvalidTransition
from app.features.conversation.fields import (
    TOTAL_BATCHES,
    all_field_keys,
    get_batch,
    get_field,
)
from app.features.conversation.repository import load_session, new_session, save_session
from app.features.conversation.schemas import QuestionOut, TurnResponse
from app.features.conversation.state_machine import transition
from app.features.conversation.states import SessionState
from app.features.extraction.router_msi import extract_batch, extract_field
from app.features.extraction.schemas import FieldType
from app.features.guardrails.input_guard import check_input
from app.features.llm.chain import LLMChain
from app.features.summary.builder import build_summary
from app.features.validation.calculator import calculate_total
from app.features.validation.validators import (
    validate_number,
    validate_text,
    validate_time,
    validate_time_sequence,
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


def _remaining_fields(session: dict) -> list:
    """Fields in the current batch not yet answered. This drives what gets re-asked - always
    the actual gaps, never the whole form again - so missing and unclear answers end up
    grouped into a single follow-up round together, however many rounds that takes."""
    return [f for f in get_batch(session["current_batch"]) if f.key not in session["answers"]]


def _collecting_response(session: dict) -> TurnResponse:
    """Builds the COLLECTING-state response: only the still-unanswered questions (so a
    follow-up round shows exactly what's left, grouped together, not the full form again),
    plus which one the client should treat as "next" and which are already answered -
    needed so a frontend (or a reloaded page / recovered session) never has to guess."""
    batch_fields = get_batch(session["current_batch"])
    answered = [f.key for f in batch_fields if f.key in session["answers"]]
    remaining = _remaining_fields(session)
    return TurnResponse(
        session_id=session["session_id"],
        state=session["state"],
        questions=[QuestionOut(key=f.key, label=f.label, question=f.question, section=f.section) for f in remaining],
        next_field_key=remaining[0].key if remaining else None,
        answered_field_keys=answered,
    )


class ConversationService:
    def __init__(self, redis_client: redis.Redis, llm_chain: LLMChain):
        self._redis = redis_client
        self._llm_chain = llm_chain

    def start_session(self, session_id: str) -> TurnResponse:
        session = new_session(session_id)
        session["state"] = transition(SessionState(session["state"]), "start").value
        save_session(self._redis, session)
        return _collecting_response(session)

    def get_session_state(self, session_id: str) -> TurnResponse:
        session = load_session(self._redis, session_id)
        return self._response_for_session(session)

    def resume_session(self, session_id: str) -> TurnResponse:
        session = load_session(self._redis, session_id)
        session["state"] = transition(SessionState(session["state"]), "resume").value
        save_session(self._redis, session)
        return self._response_for_session(session)

    def submit_answer(self, session_id: str, field_key: str, raw_text: str) -> TurnResponse:
        session = load_session(self._redis, session_id)
        current_state = SessionState(session["state"])

        if current_state not in (SessionState.COLLECTING, SessionState.CLARIFICATION):
            raise InvalidTransition(current_state.value, "answer")

        field_def = get_field(field_key)

        # Optional fields (e.g. Remarks) may legitimately have no spoken answer - accept
        # blank directly rather than bouncing it off the guardrail's empty-text rejection,
        # which would otherwise loop forever asking for a non-answer.
        if not raw_text.strip() and not field_def.required:
            return self._accept_answer(session, field_def, "", current_state)

        guard = check_input(raw_text)
        if not guard.allowed:
            return self._ask_clarification(session, field_def, f"Sorry, I didn't catch that. {field_def.question}")

        try:
            extracted = extract_field(field_def.field_type, field_def.label, raw_text, self._llm_chain, session_id)
        except AllLLMsFailed:
            session["state"] = transition(current_state, "llm_failure").value
            save_session(self._redis, session)
            raise

        if extracted.ambiguous or extracted.value is None:
            return self._ask_clarification(
                session, field_def, f"I couldn't understand that clearly. {field_def.question}"
            )

        validation = _validate_value(field_def, extracted.value)
        if not validation.valid:
            return self._ask_clarification(session, field_def, f"{validation.error}. {field_def.question}")

        return self._accept_answer(session, field_def, validation.value, current_state)

    def submit_batch_answer(self, session_id: str, raw_text: str) -> TurnResponse:
        """One transcript covering some or all of the remaining fields. Any field the LLM
        couldn't confidently extract or that fails validation is simply left unanswered -
        _advance() then reports it in `questions`, grouped with anything else still
        outstanding, so the client re-asks about exactly what's missing/unclear together on
        the next round rather than one at a time."""
        session = load_session(self._redis, session_id)
        current_state = SessionState(session["state"])

        # CLARIFICATION is accepted here too, not just COLLECTING: it's a legacy-compatible
        # alias (a session that reached CLARIFICATION via the single-field path can still be
        # driven forward by the batch endpoint - the grouped "remaining questions" design
        # works the same either way, see _remaining_fields()).
        if current_state not in (SessionState.COLLECTING, SessionState.CLARIFICATION):
            raise InvalidTransition(current_state.value, "answer_batch")

        unanswered_fields = _remaining_fields(session)
        if not unanswered_fields:
            return self._advance(session, current_state)

        guard = check_input(raw_text)
        if not guard.allowed:
            save_session(self._redis, session)
            return TurnResponse(
                session_id=session_id, state=session["state"],
                clarification_prompt="Sorry, I didn't catch that. Please try again.",
                questions=[
                    QuestionOut(key=f.key, label=f.label, question=f.question, section=f.section)
                    for f in unanswered_fields
                ],
                next_field_key=unanswered_fields[0].key,
                answered_field_keys=[f.key for f in get_batch(session["current_batch"]) if f.key in session["answers"]],
            )

        field_specs = [(f.key, f.label, f.field_type) for f in unanswered_fields]
        try:
            extracted_map = extract_batch(field_specs, raw_text, self._llm_chain, session_id)
        except AllLLMsFailed:
            session["state"] = transition(current_state, "llm_failure").value
            save_session(self._redis, session)
            raise

        for field_def in unanswered_fields:
            extracted = extracted_map[field_def.key]
            if extracted.ambiguous or extracted.value is None:
                continue
            validation = _validate_value(field_def, extracted.value)
            if not validation.valid:
                continue
            session["answers"][field_def.key] = validation.value

        return self._advance(session, current_state)

    def _accept_answer(self, session: dict, field_def, value, current_state: SessionState) -> TurnResponse:
        session["answers"][field_def.key] = value
        if session.get("pending_clarification_field") == field_def.key:
            session["pending_clarification_field"] = None
            session["state"] = transition(current_state, "clarified").value
            current_state = SessionState(session["state"])
        return self._advance(session, current_state)

    def _ask_clarification(self, session: dict, field_def, prompt: str) -> TurnResponse:
        current_state = SessionState(session["state"])
        session["pending_clarification_field"] = field_def.key
        if current_state == SessionState.COLLECTING:
            session["state"] = transition(current_state, "need_clarification").value
        save_session(self._redis, session)
        return TurnResponse(
            session_id=session["session_id"], state=session["state"],
            clarification_prompt=prompt, next_field_key=field_def.key,
        )

    def _advance(self, session: dict, current_state: SessionState) -> TurnResponse:
        answered_keys = set(session["answers"].keys())
        remaining_in_batch = [f for f in get_batch(session["current_batch"]) if f.key not in answered_keys]

        if remaining_in_batch:
            save_session(self._redis, session)
            return _collecting_response(session)

        if session["current_batch"] < TOTAL_BATCHES:
            session["current_batch"] += 1
            save_session(self._redis, session)
            return _collecting_response(session)

        missing_required = [k for k in all_field_keys() if k not in session["answers"]]
        if missing_required:
            save_session(self._redis, session)
            return _collecting_response(session)

        answers = session["answers"]
        if "vehicle_in_time" in answers and "vehicle_out_time" in answers:
            seq = validate_time_sequence(
                answers["vehicle_in_time"], answers["vehicle_out_time"], "Vehicle In Time", "Vehicle Out Time"
            )
            if not seq.valid:
                # Rejoins the "remaining" pool rather than a dedicated single-field
                # clarification, so it's grouped with anything else still outstanding on the
                # next round instead of becoming a special one-off case.
                del session["answers"]["vehicle_out_time"]
                save_session(self._redis, session)
                response = _collecting_response(session)
                response.clarification_prompt = f"{seq.error}. Please give the vehicle out time again."
                return response

        session["state"] = transition(current_state, "all_fields_collected").value
        save_session(self._redis, session)
        return self._response_for_session(session)

    def _response_for_session(self, session: dict) -> TurnResponse:
        state = SessionState(session["state"])

        if state == SessionState.AWAITING_CONFIRMATION:
            fields = dict(session["answers"])
            fields["total"] = calculate_total(
                fields["four_hand"], fields["five_hand"], fields["six_hand"],
                fields["eight_hand"], fields["cluster"],
            )
            return TurnResponse(session_id=session["session_id"], state=session["state"], summary=build_summary(fields))

        if state in (SessionState.COLLECTING, SessionState.CLARIFICATION):
            # Both states render identically: the full grouped list of remaining questions,
            # not just a single pending one - CLARIFICATION only still exists for sessions
            # that reached it via the legacy single-field path, and this keeps a
            # page-reload/resume (GET /sessions/{id}, which calls this method) consistent
            # with every other response shape.
            return _collecting_response(session)

        return TurnResponse(session_id=session["session_id"], state=session["state"])
