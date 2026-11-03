import pytest

from app.core.exceptions import ExtractionParseFailed
from app.features.extraction.router_msi import extract_field
from app.features.extraction.schemas import FieldType
from app.features.llm.base import LLMClient
from app.features.llm.chain import LLMChain


class FakeLLM(LLMClient):
    def __init__(self, response: str):
        self._response = response

    def generate(self, prompt, system=None):
        return self._response


def _chain(response: str) -> LLMChain:
    return LLMChain(primary=FakeLLM(response), backup=FakeLLM(response))


def test_extraction_always_calls_the_llm():
    # No keyword/regex shortcut sits in front of extract_field - even a plainly formatted
    # answer goes through the LLM, since understanding what counts as an answer is a judgment
    # call, not a pattern match.
    chain = _chain('{"value": 42, "display_value": 42, "ambiguous": false}')
    result = extract_field(FieldType.NUMBER, "Weight", "forty two", chain, "sess-1")
    assert result.value == 42
    assert result.source == "llm"


def test_llm_escalation_normal_value():
    chain = _chain('{"value": "14:30", "display_value": "14:30", "ambiguous": false}')
    result = extract_field(
        FieldType.TIME, "Vehicle Out Time", "around 2 or 3 in the afternoon, not totally sure", chain, "sess-2"
    )
    assert result.value == "14:30"
    assert result.source == "llm"
    assert not result.ambiguous


def test_llm_escalation_ambiguous_response():
    chain = _chain('{"value": null, "ambiguous": true}')
    result = extract_field(FieldType.TIME, "Vehicle Out Time", "uhh not sure", chain, "sess-2")
    assert result.value is None
    assert result.ambiguous


def test_llm_malformed_json_raises_parse_failed_not_silently_ambiguous():
    # Distinct from a genuinely ambiguous answer (test_llm_escalation_ambiguous_response
    # above): an unparseable response is the LLM's fault, not the user's, and the caller needs
    # to tell those apart to ask for a plain retry instead of silently discarding the answer.
    chain = _chain("not json at all")
    with pytest.raises(ExtractionParseFailed):
        extract_field(FieldType.TIME, "Vehicle Out Time", "gibberish", chain, "sess-2")
