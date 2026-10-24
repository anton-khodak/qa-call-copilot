import json

import pytest

import main
from src.clients.base import TransportError
from src.config import load_model
from src.prompts import Prompt
from tests.fakes import VALID_JSON, FakeClient, timeout_error, transcript


def test_missing_key_exits_before_any_call(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="OPENROUTER_API_KEY"):
        main.make_client(load_model("gpt4o_mini"))


def test_estimate_cost():
    ts = [transcript(text="x" * 4000), transcript(text="y" * 4000)]
    est = main.estimate_cost(ts, load_model("gpt4o_mini"), 1, Prompt("v0", "", "h"))
    assert est == pytest.approx((2 * 1000 * 0.15 + 2 * 400 * 0.60) / 1e6)


def test_run_writes_one_line_per_call(tmp_path, monkeypatch):
    client = FakeClient(VALID_JSON, TransportError(timeout_error(), 3))
    monkeypatch.setattr(main, "make_client", lambda cfg: client)
    monkeypatch.setattr(main, "load_calls", lambda split: [transcript(call_id="a"), transcript(call_id="b")])
    monkeypatch.setattr(main, "check_raw_data", lambda: None)

    main.main(["run", "--yes", "--out-dir", str(tmp_path)])

    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1 and files[0].name.endswith("_gpt4o_mini_v1_deterministic.jsonl")
    lines = [json.loads(l) for l in files[0].read_text().splitlines()]
    assert [l["call_id"] for l in lines] == ["a", "b"]
    assert {l["status"] for l in lines} == {"valid_first_try", "failed"}


def test_run_requires_raw_data(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "RAW_DIR", tmp_path / "missing")
    with pytest.raises(SystemExit, match="make data"):
        main.check_raw_data()
