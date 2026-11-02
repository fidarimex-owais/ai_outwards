from app.core.exceptions import InvalidTransition
from app.features.conversation.states import SessionState

# Allowed transitions, per the HLD:
# IDLE -> COLLECTING -> CLARIFICATION (if required) -> AWAITING_CONFIRMATION -> SAVING -> COMPLETED
# Corrections keep the session in AWAITING_CONFIRMATION. Any LLM failure pauses the session.
_TRANSITIONS: dict[SessionState, dict[str, SessionState]] = {
    SessionState.IDLE: {
        "start": SessionState.COLLECTING,
    },
    SessionState.COLLECTING: {
        "need_clarification": SessionState.CLARIFICATION,
        "all_fields_collected": SessionState.AWAITING_CONFIRMATION,
        "llm_failure": SessionState.PAUSED,
    },
    SessionState.CLARIFICATION: {
        "clarified": SessionState.COLLECTING,
        "llm_failure": SessionState.PAUSED,
        # submit_batch_answer() treats CLARIFICATION as a compatible alias of COLLECTING (a
        # session can reach CLARIFICATION via the legacy single-field path, then finish the
        # rest of the form through the batch endpoint), so it needs the same route to
        # AWAITING_CONFIRMATION that COLLECTING has.
        "all_fields_collected": SessionState.AWAITING_CONFIRMATION,
    },
    SessionState.AWAITING_CONFIRMATION: {
        "confirm": SessionState.SAVING,
        "correct": SessionState.AWAITING_CONFIRMATION,
    },
    SessionState.SAVING: {
        "save_success": SessionState.COMPLETED,
        "save_failure": SessionState.AWAITING_CONFIRMATION,
    },
    SessionState.PAUSED: {
        "resume": SessionState.COLLECTING,
    },
    SessionState.COMPLETED: {},  # terminal
}


def transition(current_state: SessionState, event: str) -> SessionState:
    allowed = _TRANSITIONS.get(current_state, {})
    if event not in allowed:
        raise InvalidTransition(current_state.value, event)
    return allowed[event]
