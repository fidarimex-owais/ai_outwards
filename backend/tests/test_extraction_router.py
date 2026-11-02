from app.features.extraction.router_msi import extract_field
from app.features.extraction.schemas import FieldType
from app.features.llm.base import LLMClient
from app.features.llm.chain import LLMChain


class ExplodingClient(LLMClient):
    """Used to prove a rule-hit never reaches the LLM."""

    def generate(self, prompt, system=None):
        raise AssertionError("LLM should NOT have been called - rule should have handled this")


def _exploding_chain() -> LLMChain:
    return LLMChain(primary=ExplodingClient(), backup=ExplodingClient())


def test_rule_hit_fields_never_reach_llm():
    chain = _exploding_chain()
    assert extract_field(FieldType.NUMBER, "Weight", "forty two", chain, "sess-1").value == 42
    assert extract_field(FieldType.VEHICLE_NUMBER, "Vehicle Number", "MH12AB1234", chain, "sess-1").value == "MH12AB1234"
    assert extract_field(FieldType.TEXT, "Company Name", "ABC Traders", chain, "sess-1").value == "ABC Traders"


class FakeLLM(LLMClient):
    def __init__(self, response: str):
        self._response = response

    def generate(self, prompt, system=None):
        return self._response


def test_llm_escalation_normal_value():
    # Deliberately a phrasing time_parse.parse_time() can't handle (no digits, no "half
    # past"/"quarter"/"o'clock" marker) - this must escalate to the LLM, not the rule.
    chain = LLMChain(primary=FakeLLM('{"value": "14:30", "ambiguous": false}'), backup=FakeLLM(""))
    result = extract_field(FieldType.TIME, "Vehicle Out Time", "around 2 or 3 in the afternoon, not totally sure", chain, "sess-2")
    assert result.value == "14:30"
    assert result.source == "llm"
    assert not result.ambiguous


def test_rule_handles_common_time_phrasing_without_llm():
    chain = _exploding_chain()
    result = extract_field(FieldType.TIME, "Vehicle Out Time", "half past two in the afternoon", chain, "sess-3")
    assert result.value == "14:30"
    assert result.source == "rule"


def test_llm_escalation_ambiguous_response():
    chain = LLMChain(primary=FakeLLM('{"value": null, "ambiguous": true}'), backup=FakeLLM(""))
    result = extract_field(FieldType.TIME, "Vehicle Out Time", "uhh not sure", chain, "sess-2")
    assert result.value is None
    assert result.ambiguous


def test_llm_escalation_malformed_json_treated_as_ambiguous():
    chain = LLMChain(primary=FakeLLM("not json at all"), backup=FakeLLM("not json at all"))
    result = extract_field(FieldType.TIME, "Vehicle Out Time", "gibberish", chain, "sess-2")
    assert result.value is None
    assert result.ambiguous
