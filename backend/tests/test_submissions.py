from app.core.mongodb import get_db
from app.features.submissions.repository import get_submission, insert_submission

from tests.test_conversation_flow import BATCH1, BATCH2, BATCH3, TIME_RESPONSES, _answer


CORRECTION_RESPONSES = {
    "Suresh Patil": '{"field_key": "labor_name", "value": "Suresh Patil", "ambiguous": false}',
    "not a plate": '{"field_key": "vehicle_number", "value": "not a plate", "ambiguous": false}',
}


def _complete_conversation(client, fake_llm, extra_responses=None):
    fake_llm(TIME_RESPONSES | (extra_responses or {}))
    session_id = client.post("/sessions").json()["session_id"]
    for batch in (BATCH1, BATCH2, BATCH3):
        for key, text in batch.items():
            last = _answer(client, session_id, key, text)
    assert last.json()["state"] == "AWAITING_CONFIRMATION"
    return session_id


def test_correction_before_confirm_updates_summary(client, fake_llm, created_sessions):
    session_id = _complete_conversation(client, fake_llm, CORRECTION_RESPONSES)
    created_sessions.append(session_id)

    r = client.patch(f"/sessions/{session_id}/correct", json={"text": "Correct the labor name to Suresh Patil"})
    data = r.json()
    assert data["state"] == "AWAITING_CONFIRMATION"
    assert "Suresh Patil" in data["summary"]


def test_correction_with_invalid_value_asks_clarification(client, fake_llm, created_sessions):
    session_id = _complete_conversation(client, fake_llm, CORRECTION_RESPONSES)
    created_sessions.append(session_id)

    r = client.patch(f"/sessions/{session_id}/correct", json={"text": "The vehicle number should be not a plate"})
    data = r.json()
    assert data["clarification_prompt"] is not None
    assert data["state"] == "AWAITING_CONFIRMATION"


def test_confirm_saves_to_mongo_and_completes_session(client, fake_llm, created_sessions):
    session_id = _complete_conversation(client, fake_llm, CORRECTION_RESPONSES)
    created_sessions.append(session_id)

    client.patch(f"/sessions/{session_id}/correct", json={"text": "Correct the labor name to Suresh Patil"})

    r = client.post(f"/sessions/{session_id}/confirm")
    assert r.status_code == 200
    submission = r.json()
    assert submission["session_id"] == session_id
    assert submission["labor_name"] == "Suresh Patil"
    assert submission["total"] == 40
    assert submission["vehicle_out_time"] == "14:30"

    db = get_db()
    doc = db["submissions"].find_one({"session_id": session_id})
    assert doc is not None
    assert doc["total"] == 40

    r = client.get(f"/sessions/{session_id}")
    assert r.json()["state"] == "COMPLETED"


def test_cannot_reconfirm_or_correct_after_completion(client, fake_llm, created_sessions):
    session_id = _complete_conversation(client, fake_llm)
    created_sessions.append(session_id)

    client.post(f"/sessions/{session_id}/confirm")

    r = client.post(f"/sessions/{session_id}/confirm")
    assert r.status_code == 409

    r = client.patch(f"/sessions/{session_id}/correct", json={"text": "Someone Else"})
    assert r.status_code == 409

    db = get_db()
    doc = db["submissions"].find_one({"session_id": session_id})
    assert doc["labor_name"] == "Ramesh Kumar"  # unchanged by the rejected attempts


def test_insert_submission_is_idempotent(client):
    db = get_db()
    sid = "pytest-idempotency-test-session"
    db["submissions"].delete_one({"session_id": sid})
    try:
        assert insert_submission(db, {"session_id": sid, "value": 1}) is True
        assert insert_submission(db, {"session_id": sid, "value": 999}) is False

        doc = get_submission(db, sid)
        assert doc["value"] == 1  # duplicate attempt did not overwrite
    finally:
        db["submissions"].delete_one({"session_id": sid})
