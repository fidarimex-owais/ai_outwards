BATCH1 = {
    "company_name": "ABC Traders", "vehicle_number": "MH12AB1234", "brand": "Chiquita",
    "line_mark": "Line Three", "weight": "twelve hundred",
}
BATCH2 = {
    "four_hand": "ten", "five_hand": "twenty", "six_hand": "five", "eight_hand": "three", "cluster": "two",
}
BATCH3 = {
    "remarks": "", "labor_name": "Ramesh Kumar",
    # vehicle_in_time has no am/pm marker and no "o'clock"/"half past" keyword -> the rule
    # can't resolve it, so it genuinely escalates to the LLM (see TIME_RESPONSES below).
    "vehicle_in_time": "the truck entered this morning at nine",
    # vehicle_out_time IS resolved by the rule (utils/time_parse.py) directly - "half past
    # two in the afternoon" needs no LLM call.
    "vehicle_out_time": "the truck left at half past two in the afternoon",
    "vehicle_for_storage": "yes", "vehicle_receiver_name": "Suresh",
}
TIME_RESPONSES = {
    "entered this morning at nine": '{"value": "09:00", "ambiguous": false}',
}


def _answer(client, session_id, field_key, text):
    return client.post(f"/sessions/{session_id}/answer", json={"field_key": field_key, "text": text})


def test_full_happy_path_reaches_awaiting_confirmation(client, fake_llm):
    # All 16 fields are shown and answered in a single "batch" now - no separate rounds.
    fake_llm(TIME_RESPONSES)

    r = client.post("/sessions")
    assert r.status_code == 200
    data = r.json()
    session_id = data["session_id"]
    assert data["state"] == "COLLECTING"
    assert len(data["questions"]) == 16  # the whole form, shown at once
    assert data["next_field_key"] == "company_name"  # first field overall
    assert data["answered_field_keys"] == []

    r = _answer(client, session_id, "company_name", "ABC Traders")
    data = r.json()
    assert data["next_field_key"] == "vehicle_number"
    assert data["answered_field_keys"] == ["company_name"]
    assert len(data["questions"]) == 15  # "questions" is always what's still remaining, not the whole form

    last = data
    for key, text in list(BATCH1.items())[1:] + list(BATCH2.items()) + list(BATCH3.items()):
        last = _answer(client, session_id, key, text).json()

    assert last["state"] == "AWAITING_CONFIRMATION"
    assert last["summary"] is not None
    assert "Total Quantity: 40" in last["summary"]
    assert "MH12AB1234" in last["summary"]
    assert "14:30" in last["summary"]

    r = client.get(f"/sessions/{session_id}")
    assert r.json()["state"] == "AWAITING_CONFIRMATION"
    assert r.json()["summary"] is not None


def test_zero_quantity_via_none_is_accepted_not_rejected(client, fake_llm):
    # Regression test: "cluster is none" was being rejected as unclear instead of accepted
    # as 0 - a declined quantity is a valid answer, not a missing one.
    fake_llm({})  # should resolve via the rule, no LLM call needed
    session_id = client.post("/sessions").json()["session_id"]

    r = _answer(client, session_id, "cluster", "none")
    data = r.json()
    assert data["state"] != "CLARIFICATION"
    assert "cluster" in data["answered_field_keys"]


def test_clarification_loop_on_invalid_answer(client, fake_llm):
    fake_llm({})
    session_id = client.post("/sessions").json()["session_id"]

    r = _answer(client, session_id, "vehicle_number", "not a plate at all")
    data = r.json()
    assert data["state"] == "CLARIFICATION"
    assert data["clarification_prompt"] is not None
    assert data["next_field_key"] == "vehicle_number"  # client knows exactly what to re-record

    r = _answer(client, session_id, "vehicle_number", "MH14XY9999")
    assert r.json()["state"] == "COLLECTING"


def test_session_recovery_mid_batch_shows_correct_next_field(client, fake_llm):
    fake_llm({})
    session_id = client.post("/sessions").json()["session_id"]

    _answer(client, session_id, "company_name", "ABC Traders")
    _answer(client, session_id, "vehicle_number", "MH12AB1234")

    # simulate a page reload: nothing client-side, ask the server fresh
    r = client.get(f"/sessions/{session_id}")
    data = r.json()
    assert data["state"] == "COLLECTING"
    assert data["next_field_key"] == "brand"  # third field of batch 1, correctly resumed
    assert data["answered_field_keys"] == ["company_name", "vehicle_number"]


def test_all_llms_failed_pauses_session_and_resume_recovers(client, fake_llm):
    from app.features.llm.base import LLMClient
    from app.features.llm.chain import LLMChain, get_llm_chain
    from app.main import app

    class AlwaysFailLLM(LLMClient):
        def generate(self, prompt, system=None):
            raise RuntimeError("simulated total outage")

    app.dependency_overrides[get_llm_chain] = lambda: LLMChain(primary=AlwaysFailLLM(), backup=AlwaysFailLLM())

    session_id = client.post("/sessions").json()["session_id"]

    # vehicle_out_time has no Python rule -> must escalate to the (failing) LLM
    r = _answer(client, session_id, "vehicle_out_time", "around three in the afternoon")
    assert r.status_code == 503

    r = client.get(f"/sessions/{session_id}")
    assert r.json()["state"] == "PAUSED"

    r = client.post(f"/sessions/{session_id}/resume")
    assert r.json()["state"] == "COLLECTING"


def test_time_sequence_validation_rejects_out_before_in(client, fake_llm):
    fake_llm({
        "entered at two in the afternoon": '{"value": "14:00", "ambiguous": false}',
        "left at five in the morning": '{"value": "05:00", "ambiguous": false}',
        "left at four in the afternoon": '{"value": "16:00", "ambiguous": false}',
    })
    session_id = client.post("/sessions").json()["session_id"]

    for key, text in BATCH1.items():
        _answer(client, session_id, key, text)
    for key, text in BATCH2.items():
        _answer(client, session_id, key, text)
    _answer(client, session_id, "remarks", "")
    _answer(client, session_id, "labor_name", "Ramesh")
    _answer(client, session_id, "vehicle_for_storage", "yes")
    _answer(client, session_id, "vehicle_receiver_name", "Suresh")

    _answer(client, session_id, "vehicle_in_time", "the truck entered at two in the afternoon")
    r = _answer(client, session_id, "vehicle_out_time", "the truck left at five in the morning")
    data = r.json()
    # Rejoins the "remaining" pool instead of a dedicated single-field clarification state -
    # grouped with whatever else is outstanding, not a special case.
    assert data["state"] == "COLLECTING"
    assert data["clarification_prompt"] is not None
    assert data["next_field_key"] == "vehicle_out_time"

    r = _answer(client, session_id, "vehicle_out_time", "the truck left at four in the afternoon")
    assert r.json()["state"] == "AWAITING_CONFIRMATION"
