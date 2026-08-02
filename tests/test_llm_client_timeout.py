"""config.yaml's llm.timeout_seconds must actually reach the Anthropic client.

The key has shipped in config.yaml since the beginning but nothing read it, so
Claude calls ran with no timeout of ours at all -- a stalled connection could
hang a whole benchmark run with no bound.
"""

import sys
import types

import pytest

from src.config.settings import Settings
from src.llm.client import DEFAULT_TIMEOUT_SECONDS


@pytest.fixture
def fake_anthropic(monkeypatch):
    """A stand-in SDK that records how Anthropic() was constructed."""
    recorded = {}

    class _Anthropic:
        def __init__(self, **kwargs):
            recorded.update(kwargs)
            self.messages = types.SimpleNamespace()

    module = types.ModuleType("anthropic")
    module.Anthropic = _Anthropic
    for name in ("AuthenticationError", "APIStatusError", "APIConnectionError",
                 "APITimeoutError"):
        setattr(module, name, type(name, (Exception,), {}))
    monkeypatch.setitem(sys.modules, "anthropic", module)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    return recorded


def test_timeout_is_passed_to_the_sdk(fake_anthropic):
    from src.llm.client import LLMClient

    LLMClient(timeout=12.5)
    assert fake_anthropic["timeout"] == 12.5
    assert fake_anthropic["max_retries"] == 3


def test_default_timeout_is_applied_when_unspecified(fake_anthropic):
    from src.llm.client import LLMClient

    LLMClient()
    assert fake_anthropic["timeout"] == DEFAULT_TIMEOUT_SECONDS


def test_settings_reads_the_configured_value():
    settings = Settings(raw={"llm": {"timeout_seconds": 90}})
    assert settings.llm_timeout_seconds == 90.0


def test_settings_falls_back_to_the_client_default():
    assert Settings(raw={}).llm_timeout_seconds == DEFAULT_TIMEOUT_SECONDS


def test_shipped_config_value_reaches_the_client():
    """End to end: config.yaml -> Settings -> the value the orchestrator uses."""
    from src.config.settings import load_settings

    settings = load_settings()
    raw = settings.raw["llm"]["timeout_seconds"]
    assert settings.llm_timeout_seconds == float(raw)


def test_timeout_error_is_reported_as_such(fake_anthropic, monkeypatch):
    """A timeout must say so, not surface as a generic connection error."""
    import anthropic

    from src.llm.client import LLMClient, LLMResponseError

    client = LLMClient(timeout=5)

    def boom(**kwargs):
        raise anthropic.APITimeoutError()

    client.client.messages.create = boom
    with pytest.raises(LLMResponseError, match="did not respond within 5"):
        client.extract_json("prompt", schema={"type": "object"})
