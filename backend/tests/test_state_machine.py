import pytest

from app.core.exceptions import InvalidTransition
from app.features.conversation.state_machine import transition
from app.features.conversation.states import SessionState


def test_full_happy_path():
    s = SessionState.IDLE
    s = transition(s, "start")
    assert s == SessionState.COLLECTING

    s = transition(s, "need_clarification")
    assert s == SessionState.CLARIFICATION

    s = transition(s, "clarified")
    assert s == SessionState.COLLECTING

    s = transition(s, "all_fields_collected")
    assert s == SessionState.AWAITING_CONFIRMATION

    s = transition(s, "correct")
    assert s == SessionState.AWAITING_CONFIRMATION

    s = transition(s, "confirm")
    assert s == SessionState.SAVING

    s = transition(s, "save_success")
    assert s == SessionState.COMPLETED


def test_terminal_state_rejects_any_transition():
    with pytest.raises(InvalidTransition):
        transition(SessionState.COMPLETED, "start")


def test_invalid_event_rejected():
    with pytest.raises(InvalidTransition):
        transition(SessionState.COLLECTING, "confirm")


def test_paused_and_resume_path():
    s = transition(SessionState.COLLECTING, "llm_failure")
    assert s == SessionState.PAUSED

    s = transition(s, "resume")
    assert s == SessionState.COLLECTING


def test_clarification_can_complete_directly_to_awaiting_confirmation():
    # CLARIFICATION is a compatible alias of COLLECTING for the batch endpoint - a session
    # that finishes its last remaining field from this state must reach AWAITING_CONFIRMATION
    # the same way COLLECTING does, not hit a dead end.
    s = transition(SessionState.CLARIFICATION, "all_fields_collected")
    assert s == SessionState.AWAITING_CONFIRMATION


def test_save_failure_returns_to_awaiting_confirmation():
    s = transition(SessionState.SAVING, "save_failure")
    assert s == SessionState.AWAITING_CONFIRMATION
