import json
import os
from types import SimpleNamespace

import httpx2
import openai
import pytest

from src.clients.base import TransportError
from src.clients.provider import ProviderClient
from src.clients.retry import call_with_retry
from src.config import load_model, load_sampling
from src.schema import CallQARecord, strict_json_schema


class FakeSDK:
    """Stands in for openai.OpenAI: chat.completions.create returns/raises queued items."""

    def __init__(self, *items, content='{"x":1}', prompt_tokens=1200, completion_tokens=150):
        self.items = list(items)
        self.calls = 0
        self.last_kwargs = None
        self.response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
        )
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        if self.items:
            raise self.items.pop(0)
        return self.response


def _timeout():
    return openai.APITimeoutError(request=httpx2.Request("POST", "https://openrouter.ai"))


def _client(sdk):
    c = ProviderClient(load_model("gpt4o_mini"), "k", sdk=sdk)
    c.sleep = lambda s: None
    return c


def test_retry_succeeds_on_third_attempt():
    calls, sleeps = [], []

    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise TimeoutError()
        return "ok"

    assert call_with_retry(fn, 3, (TimeoutError,), sleep=sleeps.append) == "ok"
    assert sleeps == [1.0, 2.0]


def test_retry_exhausted_raises_transport_error():
    def fn():
        raise TimeoutError()

    with pytest.raises(TransportError) as e:
        call_with_retry(fn, 3, (TimeoutError,), sleep=lambda s: None)
    assert e.value.attempts == 3 and isinstance(e.value.last, TimeoutError)


def test_non_retryable_propagates_immediately():
    calls, sleeps = [], []

    def fn():
        calls.append(1)
        raise ValueError("bad")

    with pytest.raises(ValueError):
        call_with_retry(fn, 3, (TimeoutError,), sleep=sleeps.append)
    assert len(calls) == 1 and sleeps == []


def test_provider_request_shape():
    fake = FakeSDK()
    out = _client(fake).complete("SYS", "USER", {"type": "object"}, load_sampling("deterministic"))
    kw = fake.last_kwargs
    assert kw["model"] == "openai/gpt-4o-mini" and kw["temperature"] == 0.0 and kw["top_p"] == 1.0 and kw["seed"] == 42
    assert kw["timeout"] == 60
    assert kw["response_format"]["type"] == "json_schema" and kw["response_format"]["json_schema"]["strict"] is True
    assert kw["response_format"]["json_schema"]["schema"] == {"type": "object"}
    assert kw["messages"] == [{"role": "system", "content": "SYS"}, {"role": "user", "content": "USER"}]
    assert (out.text, out.input_tokens, out.output_tokens) == ('{"x":1}', 1200, 150)


def test_provider_retries_timeouts():
    fake = FakeSDK(_timeout(), _timeout())
    out = _client(fake).complete("S", "U", {}, load_sampling("deterministic"))
    assert fake.calls == 3 and out.text == '{"x":1}'


def test_provider_none_content_returned_as_none():
    out = _client(FakeSDK(content=None)).complete("S", "U", {}, load_sampling("deterministic"))
    assert out.text is None


@pytest.mark.live
def test_live_smoke():
    from dotenv import load_dotenv

    load_dotenv()
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        pytest.skip("OPENROUTER_API_KEY not set")
    c = ProviderClient(load_model("gpt4o_mini"), key)
    transcript = "Thank you for calling, this call is recorded. I want a quote for my car insurance. Sure, what's your zip?"
    out = c.complete("Extract a QA record.", transcript, strict_json_schema(), load_sampling("deterministic"))
    CallQARecord.model_validate(json.loads(out.text))
    assert out.input_tokens > 0


def test_provider_no_choices_retried_then_transport_error():
    # OpenRouter can return HTTP 200 with {"error": ...} and no choices when the upstream fails
    fake = FakeSDK()
    fake.response = SimpleNamespace(choices=None, usage=None, error={"message": "upstream failed"})
    with pytest.raises(TransportError) as e:
        _client(fake).complete("S", "U", {}, load_sampling("deterministic"))
    assert fake.calls == 3 and "upstream failed" in str(e.value)
