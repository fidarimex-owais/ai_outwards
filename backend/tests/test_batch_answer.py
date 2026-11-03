import json

from tests.test_conversation_flow import BATCH1, BATCH2, BATCH3, FIELD_RESPONSES

ALL_16_KEYS = [
    "company_name", "vehicle_number", "brand", "line_mark", "weight",
    "four_hand", "five_hand", "six_hand", "eight_hand", "cluster",
    "remarks", "labor_name", "vehicle_out_time", "vehicle_in_time",
    "vehicle_for_storage", "vehicle_receiver_name",
]


def _fake_batch_response(overrides: dict) -> str:
    """Builds a full-form (all 16 fields) JSON response, defaulting every field not in
    overrides to ambiguous/null."""
    data = {}
    for key in ALL_16_KEYS:
        if key in overrides:
            data[key] = {"value": overrides[key], "ambiguous": False}
        else:
            data[key] = {"value": None, "ambiguous": True}
    return json.dumps(data)


def test_full_batch_answered_in_one_call_reaches_awaiting_confirmation(client, fake_llm):
    # The whole 16-field form, answered from a single recording - this is the actual
    # feature: one long utterance covering everything, one LLM call, straight to summary.
    fake_llm({
        "company": _fake_batch_response({
            "company_name": "Khorale Global", "vehicle_number": "MH12AB1234", "brand": "Joker Banana",
            "line_mark": "Line Three", "weight": 1200,
            "four_hand": 10, "five_hand": 20, "six_hand": 5, "eight_hand": 3, "cluster": 2,
            "remarks": "", "labor_name": "Ramesh Kumar",
            "vehicle_out_time": "14:30", "vehicle_in_time": "09:00",
            "vehicle_for_storage": "yes", "vehicle_receiver_name": "Suresh",
        }),
    })
    session_id = client.post("/sessions").json()["session_id"]

    r = client.post(f"/sessions/{session_id}/answer-batch", json={
        "text": "company Khorale Global, vehicle MH12AB1234, brand Joker Banana, line mark Line Three, weight twelve hundred, "
                "four hand ten, five hand twenty, six hand five, eight hand three, cluster two, "
                "no remarks, labor Ramesh Kumar, out time half past two, in time nine AM, for storage yes, receiver Suresh"
    })
    data = r.json()
    assert data["state"] == "AWAITING_CONFIRMATION"
    assert data["summary"] is not None
    assert "Total Quantity: 40" in data["summary"]
    assert "MH12AB1234" in data["summary"]


def test_partial_batch_regroups_just_the_missed_ones(client, fake_llm):
    # weight is "ambiguous" in the fake response - everything else succeeds
    fake_llm({
        "company": _fake_batch_response({
            "company_name": "Khorale Global", "vehicle_number": "MH12AB1234", "brand": "Joker Banana",
            "line_mark": "Line Three",
            "four_hand": 10, "five_hand": 20, "six_hand": 5, "eight_hand": 3, "cluster": 2,
            "remarks": "", "labor_name": "Ramesh Kumar",
            "vehicle_out_time": "14:30", "vehicle_in_time": "09:00",
            "vehicle_for_storage": "yes", "vehicle_receiver_name": "Suresh",
        }),
    })
    session_id = client.post("/sessions").json()["session_id"]

    r = client.post(f"/sessions/{session_id}/answer-batch", json={
        "text": "company Khorale Global vehicle MH12AB1234 brand Joker Banana line mark Line Three, didn't catch the weight, "
                "and everything else"
    })
    data = r.json()
    assert data["state"] == "COLLECTING"
    assert data["questions"] == [{
        "key": "weight", "label": "Weight", "question": "What is the weight, in kilograms?",
        "section": "Company & Vehicle Details",
    }]  # only what's still missing is grouped into the follow-up, not the whole form again
    assert data["next_field_key"] == "weight"

    # finish the missed field individually, via the existing single-field endpoint - this
    # replaces the installed LLM chain, so it needs its own canned response too now that
    # extract_field always calls the LLM.
    fake_llm({'"1200"': '{"value": 1200, "ambiguous": false}'})
    r = client.post(f"/sessions/{session_id}/answer", json={"field_key": "weight", "text": "1200"})
    assert r.json()["state"] == "AWAITING_CONFIRMATION"  # that was the last field


def test_three_missed_fields_grouped_into_one_followup_and_resolved_together(client, fake_llm):
    """The exact scenario from the spec: miss three fields in the first recording, they get
    grouped into one follow-up message (not asked one at a time), and a second recording
    answering all three together resolves all of them in one call."""
    fake_llm({
        "company": _fake_batch_response({
            "company_name": "Khorale Global", "vehicle_number": "MH12AB1234", "brand": "Joker Banana",
            "line_mark": "Line Three", "weight": 1200,
            "four_hand": 10, "five_hand": 20, "six_hand": 5, "eight_hand": 3, "cluster": 2,
            "labor_name": "Ramesh Kumar",
            "vehicle_out_time": "14:30", "vehicle_in_time": "09:00",
            "vehicle_for_storage": "yes",
            # remarks, vehicle_receiver_name deliberately left out -> ambiguous/missing
        }),
    })
    session_id = client.post("/sessions").json()["session_id"]

    r = client.post(f"/sessions/{session_id}/answer-batch", json={"text": "company Khorale Global, everything else as usual"})
    data = r.json()
    assert data["state"] == "COLLECTING"
    missed_keys = {q["key"] for q in data["questions"]}
    assert missed_keys == {"remarks", "vehicle_receiver_name"}  # both grouped together, in one message
    assert len(data["answered_field_keys"]) == 14

    # second recording answers both remaining ones together, in one call
    fake_llm({
        "none": _fake_batch_response({"remarks": "", "vehicle_receiver_name": "Suresh"}),
    })
    r = client.post(f"/sessions/{session_id}/answer-batch", json={"text": "none for remarks, receiver is Suresh"})
    data = r.json()
    assert data["state"] == "AWAITING_CONFIRMATION"
    assert "Suresh" in data["summary"]


def test_batch_answer_accepted_from_clarification_state(client, fake_llm):
    """Regression test: a session that reached CLARIFICATION via the legacy single-field
    path (e.g. one created before this behavior existed, found sitting in Redis on resume)
    must still be drivable through the batch endpoint - CLARIFICATION is a compatible alias
    of COLLECTING for answer-batch purposes, not a dead end."""
    fake_llm({
        "company": _fake_batch_response({
            "company_name": "Khorale Global", "vehicle_number": "MH12AB1234", "brand": "Joker Banana",
            "line_mark": "Line Three", "weight": 1200,
            "four_hand": 10, "five_hand": 20, "six_hand": 5, "eight_hand": 3, "cluster": 2,
            "remarks": "", "labor_name": "Ramesh Kumar",
            "vehicle_out_time": "14:30", "vehicle_in_time": "09:00",
            "vehicle_for_storage": "yes", "vehicle_receiver_name": "Suresh",
        }),
    })
    session_id = client.post("/sessions").json()["session_id"]
    # an invalid vehicle number forces CLARIFICATION via the legacy single-field endpoint
    r = client.post(f"/sessions/{session_id}/answer", json={"field_key": "vehicle_number", "text": "garbage"})
    assert r.json()["state"] == "CLARIFICATION"

    # the resume path (GET) must show the full grouped list, not just the one pending field
    r = client.get(f"/sessions/{session_id}")
    data = r.json()
    assert len(data["questions"]) == 16
    assert data["next_field_key"] == "company_name"

    # and the batch endpoint must still accept a recording from this state
    r = client.post(f"/sessions/{session_id}/answer-batch", json={
        "text": "company Khorale Global, vehicle MH12AB1234, brand Joker Banana, line mark Line Three, weight twelve hundred, "
                "four hand ten, five hand twenty, six hand five, eight hand three, cluster two, "
                "no remarks, labor Ramesh Kumar, out time half past two, in time nine AM, for storage yes, receiver Suresh"
    })
    assert r.json()["state"] == "AWAITING_CONFIRMATION"


def test_batch_answer_rejected_outside_collecting_or_clarification_state(client, fake_llm):
    fake_llm(FIELD_RESPONSES)
    session_id = client.post("/sessions").json()["session_id"]
    for batch in (BATCH1, BATCH2, BATCH3):
        for key, text in batch.items():
            last = client.post(f"/sessions/{session_id}/answer", json={"field_key": key, "text": text})
    assert last.json()["state"] == "AWAITING_CONFIRMATION"

    r = client.post(f"/sessions/{session_id}/answer-batch", json={"text": "anything"})
    assert r.status_code == 409  # InvalidTransition - AWAITING_CONFIRMATION is genuinely incompatible


def test_batch_guardrail_rejects_empty_input(client, fake_llm):
    fake_llm({})
    session_id = client.post("/sessions").json()["session_id"]
    r = client.post(f"/sessions/{session_id}/answer-batch", json={"text": "   "})
    data = r.json()
    assert data["state"] == "COLLECTING"
    assert data["clarification_prompt"] is not None
    assert data["next_field_key"] == "company_name"


def test_batch_all_llms_failed_pauses_session(client):
    from app.features.llm.base import LLMClient
    from app.features.llm.chain import LLMChain, get_llm_chain
    from app.main import app

    class AlwaysFailLLM(LLMClient):
        def generate(self, prompt, system=None):
            raise RuntimeError("simulated outage")

    app.dependency_overrides[get_llm_chain] = lambda: LLMChain(primary=AlwaysFailLLM(), backup=AlwaysFailLLM())

    session_id = client.post("/sessions").json()["session_id"]
    r = client.post(f"/sessions/{session_id}/answer-batch", json={"text": "company Khorale Global"})
    assert r.status_code == 503

    r = client.get(f"/sessions/{session_id}")
    assert r.json()["state"] == "PAUSED"
