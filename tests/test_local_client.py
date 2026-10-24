import json

import httpx2
import pytest

from src.clients.base import FatalClientError, RequestError, TransportError
from src.clients.local import OllamaClient
from src.config import load_model, load_sampling


class Server:
    """httpx2 MockTransport handler: returns queued (status, body) or raises queued exceptions."""

    def __init__(self, *items):
        self.items = list(items)
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        item = self.items.pop(0)
        if isinstance(item, BaseException):
            raise item
        status, body = item
        return httpx2.Response(status, json=body)


def chat_ok(content='{"x":1}', prompt=900, out=120):
    return 200, {"message": {"role": "assistant", "content": content}, "prompt_eval_count": prompt, "eval_count": out}


def _client(server):
    c = OllamaClient(load_model("qwen3_8b"), "http://ollama:11434",
                     http=httpx2.Client(transport=httpx2.MockTransport(server)))
    c.sleep = lambda s: None
    return c


def test_local_config():
    m = load_model("qwen3_8b")
    assert (m.provider, m.model_id, m.price_input_per_1m, m.price_output_per_1m) == ("ollama", "qwen3:8b", 0, 0)
    assert m.context_tokens == 16384 and m.max_attempts == 3 and m.timeout_s >= 300
    assert m.max_output_tokens == 1024


def test_low_sampling():
    s = load_sampling("low")
    assert (s.temperature, s.top_p, s.seed) == (0.3, 0.9, 42)


def test_request_shape_same_schema_thinking_off():
    server = Server(chat_ok())
    out = _client(server).complete("SYS", "USER", {"type": "object"}, load_sampling("low"))
    req = server.requests[0]
    body = json.loads(req.content)
    assert str(req.url) == "http://ollama:11434/api/chat"
    assert body["model"] == "qwen3:8b" and body["stream"] is False and body["think"] is False
    assert body["format"] == {"type": "object"}
    assert body["messages"] == [{"role": "system", "content": "SYS"}, {"role": "user", "content": "USER"}]
    assert body["options"] == {"temperature": 0.3, "top_p": 0.9, "seed": 42, "num_ctx": 16384, "num_predict": 1024}
    assert (out.text, out.input_tokens, out.output_tokens, out.warnings) == ('{"x":1}', 900, 120, [])


def test_timeouts_retried():
    server = Server(httpx2.ReadTimeout("slow"), (503, {"error": "busy"}), chat_ok())
    out = _client(server).complete("S", "U", {}, load_sampling("deterministic"))
    assert len(server.requests) == 3 and out.text == '{"x":1}'


def test_retries_exhausted():
    server = Server(*[httpx2.ConnectError("refused")] * 3)
    with pytest.raises(TransportError):
        _client(server).complete("S", "U", {}, load_sampling("deterministic"))


def test_400_is_request_error():
    with pytest.raises(RequestError, match="HTTP 400"):
        _client(Server((400, {"error": "invalid format"}))).complete("S", "U", {}, load_sampling("deterministic"))


def test_missing_model_is_fatal():
    with pytest.raises(FatalClientError, match="ollama pull qwen3:8b"):
        _client(Server((404, {"error": "model 'qwen3:8b' not found"}))).complete("S", "U", {}, load_sampling("deterministic"))


def test_context_full_warns():
    # Ollama silently truncates input beyond num_ctx; flag it instead of scoring a truncated call as normal
    out = _client(Server(chat_ok(prompt=16384))).complete("S", "U", {}, load_sampling("deterministic"))
    assert out.warnings == ["context_full:16384"]


def test_check_ready_model_missing():
    server = Server((200, {"models": [{"name": "llama3:8b"}]}))
    with pytest.raises(FatalClientError, match="ollama pull qwen3:8b"):
        _client(server).check_ready()


def test_check_ready_server_down():
    with pytest.raises(FatalClientError, match="ollama serve"):
        _client(Server(httpx2.ConnectError("refused"))).check_ready()


def test_output_cap_hit_warns():
    """qwen3 can loop inside the objections list; the num_predict cap ends it and is flagged."""
    status, body = chat_ok(content='{"objections": [{"type"', out=1024)
    body["done_reason"] = "length"
    out = _client(Server((status, body))).complete("S", "U", {}, load_sampling("deterministic"))
    assert out.warnings == ["output_truncated:1024"]
