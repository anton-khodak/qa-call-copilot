import json

import pytest

from src.clients.base import Completion, FatalClientError, RequestError, TransportError
from src.config import load_model, load_sampling
from src.extract import ExtractionResult, extract
from src.prompts import load_prompt
from src.results import append_jsonl, build_record, cost_usd
from src.schema import CallQARecord
from tests.fakes import VALID_JSON, FakeClient, timeout_error, transcript
from tests.test_schema import VALID

P = load_prompt("v1")
S = load_sampling("deterministic")


def _run(*items, t=None):
    return extract(FakeClient(*items), t or transcript(), P, S)


def test_valid_output():
    r = _run(VALID_JSON)
    assert r.status == "valid_first_try"
    assert r.parsed == CallQARecord.model_validate(VALID).model_dump(mode="json")
    assert r.latency_ms >= 0 and (r.input_tokens, r.output_tokens) == (1000, 200)


def test_sends_prompt_and_wrapped_transcript():
    client = FakeClient(VALID_JSON)
    extract(client, transcript(text="raw text"), P, S)
    system, user, schema, sampling = client.calls[0]
    assert system == P.text and user == "<transcript>\nraw text\n</transcript>"
    assert schema["title"] == "CallQARecord" and sampling == S


def test_invalid_enum_failed():
    raw = json.dumps({**VALID, "outcome": "maybe"})
    r = _run(raw)
    assert r.status == "failed" and r.parsed is None and r.raw_output == raw
    assert r.warnings[0].startswith("validation_error")


def test_prose_output_failed():
    r = _run("Sure! Here is the record you asked for.")
    assert r.status == "failed" and r.raw_output == "Sure! Here is the record you asked for."


def test_none_content_failed():
    r = _run(None)
    assert r.status == "failed" and r.warnings == ["empty_output"]


def test_transport_error_failed():
    r = _run(TransportError(timeout_error(), 3))
    assert r.status == "failed" and r.raw_output is None
    assert r.warnings == ["transport_error:APITimeoutError"]


def test_request_error_failed():
    r = _run(RequestError("BadRequestError", "bad schema"))
    assert r.status == "failed" and r.warnings == ["request_error:BadRequestError"]


def test_backend_warnings_kept():
    r = _run(Completion(VALID_JSON, 10, 5, ["context_full"]))
    assert r.status == "valid_first_try" and r.warnings == ["context_full"]


def test_checks_appended():
    r = _run(VALID_JSON, t=transcript(domain="auto_insurance"))
    assert r.status == "valid_first_try"
    assert "domain_mismatch:predicted=medicare,source=auto_insurance" in r.warnings


def test_cost():
    assert cost_usd(1_000_000, 1_000_000, load_model("gpt4o_mini")) == pytest.approx(0.75)


def _record():
    res = ExtractionResult("valid_first_try", {"a": 1}, "{}", [], 5, 1000, 200)
    return build_record("run1", transcript(), load_model("gpt4o_mini"), P, S, 0, res)


def test_record_keys_match_spec():
    keys = ["run_id", "timestamp", "call_id", "split", "model", "provider", "prompt_version", "prompt_hash",
            "schema_version", "sampling_name", "temperature", "top_p", "run_idx", "status", "latency_ms",
            "input_tokens", "output_tokens", "cost_usd", "warnings", "raw_output", "parsed"]
    rec = _record()
    assert list(rec.keys()) == keys
    assert (rec["model"], rec["provider"], rec["prompt_hash"], rec["schema_version"]) == (
        "openai/gpt-4o-mini", "openrouter", P.hash, "v1")
    assert rec["cost_usd"] == pytest.approx((1000 * 0.15 + 200 * 0.60) / 1e6)


def test_append_jsonl(tmp_path):
    p = tmp_path / "runs" / "r.jsonl"
    append_jsonl(p, _record())
    append_jsonl(p, _record())
    lines = p.read_text().splitlines()
    assert len(lines) == 2 and all(json.loads(l)["run_id"] == "run1" for l in lines)


def test_unexpected_exception_failed_not_raised():
    r = _run(RuntimeError("boom"))
    assert r.status == "failed" and r.warnings == ["unexpected_error:RuntimeError: boom"]


def test_fatal_client_error_propagates():
    with pytest.raises(FatalClientError):
        _run(FatalClientError("AuthenticationError (401)"))
