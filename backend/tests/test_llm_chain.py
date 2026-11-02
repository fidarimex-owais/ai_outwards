import pytest

from app.core.exceptions import AllLLMsFailed
from app.features.llm.base import LLMClient
from app.features.llm.chain import LLMChain

# Fakes only in the automated suite - no real API calls on every test run (cost, network
# flakiness, determinism). Live Gemini/Groq/chain behavior was manually verified in Step 9
# and is documented in BUILD_LOG.md; re-verify live manually if either provider's API changes.


class WorkingClient(LLMClient):
    def generate(self, prompt, system=None):
        return f"response-to: {prompt}"


class FailingClient(LLMClient):
    def generate(self, prompt, system=None):
        raise RuntimeError("simulated provider failure")


def test_primary_success_backup_never_called():
    class ExplodingClient(LLMClient):
        def generate(self, prompt, system=None):
            raise AssertionError("backup should not have been called")

    chain = LLMChain(primary=WorkingClient(), backup=ExplodingClient())
    assert chain.generate("hello") == "response-to: hello"


def test_primary_fails_falls_back_to_backup():
    chain = LLMChain(primary=FailingClient(), backup=WorkingClient())
    assert chain.generate("hello") == "response-to: hello"


def test_both_fail_raises_all_llms_failed():
    chain = LLMChain(primary=FailingClient(), backup=FailingClient())
    with pytest.raises(AllLLMsFailed):
        chain.generate("hello", session_id="sess-123")
