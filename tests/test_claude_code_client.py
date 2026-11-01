import json
import subprocess

import pytest

from src.clients.base import FatalClientError, RequestError, TransportError
from src.clients.claude_code import ClaudeCodeClient
from src.config import load_model, load_sampling
from tests.test_schema import VALID

DEFAULT = load_sampling("cli_default")


def result_json(structured=VALID, cost=0.04, is_error=False, api_status=None, result=""):
    return json.dumps({
        "type": "result", "is_error": is_error, "api_error_status": api_status, "result": result,
        "structured_output": structured, "total_cost_usd": cost,
        "usage": {"input_tokens": 2, "cache_creation_input_tokens": 3000, "cache_read_input_tokens": 800,
                  "output_tokens": 600},
    })


class Runner:
    """subprocess.run stand-in: returns queued CompletedProcess or raises queued exceptions."""

    def __init__(self, *items):
        self.items = list(items)
        self.calls = []

    def __call__(self, cmd, **kw):
        self.calls.append((cmd, kw))
        item = self.items.pop(0)
        if isinstance(item, BaseException):
            raise item
        code, out = item
        return subprocess.CompletedProcess(cmd, code, stdout=out, stderr="")


def client(*items):
    c = ClaudeCodeClient(load_model("opus_5_5"), runner=Runner(*items))
    c.sleep = lambda s: None
    return c


def test_structured_output_tokens_and_reported_cost():
    c = client((0, result_json()))
    comp = c.complete("SYS", "<transcript>x</transcript>", {"type": "object"}, DEFAULT)
    assert json.loads(comp.text) == VALID
    assert (comp.input_tokens, comp.output_tokens, comp.cost_usd) == (3802, 600, 0.04)


def test_command_is_isolated_and_passes_prompt_schema_and_transcript():
    c = client((0, result_json()))
    c.complete("SYS", "<transcript>x</transcript>", {"type": "object"}, DEFAULT)
    cmd, kw = c.runner.calls[0]
    args = dict(zip(cmd, cmd[1:]))
    assert cmd[:2] == ["claude", "-p"]
    assert args["--model"] == "claude-opus-5-5" and args["--system-prompt"] == "SYS"
    assert json.loads(args["--json-schema"]) == {"type": "object"}
    assert args["--tools"] == "" and args["--setting-sources"] == ""
    assert "--strict-mcp-config" in cmd and "--no-session-persistence" in cmd
    assert kw["input"] == "<transcript>x</transcript>" and kw["timeout"] == c.config.timeout_s
    assert kw["cwd"] != str(c.repo_root)  # no CLAUDE.md or project settings picked up


def test_sampling_with_temperature_is_rejected():
    with pytest.raises(FatalClientError, match="temperature"):
        client().complete("S", "U", {}, load_sampling("deterministic"))


def test_timeout_is_retried_then_transport_error():
    c = client(subprocess.TimeoutExpired("claude", 1), subprocess.TimeoutExpired("claude", 1),
               subprocess.TimeoutExpired("claude", 1))
    with pytest.raises(TransportError):
        c.complete("S", "U", {}, DEFAULT)
    assert len(c.runner.calls) == c.config.max_attempts


def test_overloaded_is_retried():
    c = client((1, result_json(is_error=True, api_status=529, structured=None)), (0, result_json()))
    assert json.loads(c.complete("S", "U", {}, DEFAULT).text) == VALID


def test_not_logged_in_is_fatal():
    c = client((1, result_json(is_error=True, structured=None, result="Not logged in · Please run /login")))
    with pytest.raises(FatalClientError, match="login"):
        c.complete("S", "U", {}, DEFAULT)


def test_other_error_is_request_error():
    c = client((1, result_json(is_error=True, api_status=400, structured=None, result="bad request")))
    with pytest.raises(RequestError):
        c.complete("S", "U", {}, DEFAULT)


def test_missing_structured_output_falls_back_to_result_text():
    c = client((0, result_json(structured=None, result="not json")))
    assert c.complete("S", "U", {}, DEFAULT).text == "not json"
