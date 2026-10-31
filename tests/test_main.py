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


def test_auth_error_aborts_run_without_results_file(tmp_path, monkeypatch):
    from src.clients.base import FatalClientError

    client = FakeClient(VALID_JSON, FatalClientError("AuthenticationError (401)"))
    monkeypatch.setattr(main, "make_client", lambda cfg: client)
    monkeypatch.setattr(main, "load_calls", lambda split: [transcript(call_id="a"), transcript(call_id="b")])
    monkeypatch.setattr(main, "check_raw_data", lambda: None)

    with pytest.raises(SystemExit, match="AuthenticationError"):
        main.main(["run", "--yes", "--out-dir", str(tmp_path)])
    assert list(tmp_path.glob("*.jsonl")) == []


def _patch_run(monkeypatch, client, calls):
    monkeypatch.setattr(main, "make_client", lambda cfg: client)
    monkeypatch.setattr(main, "load_calls", lambda split: calls)
    monkeypatch.setattr(main, "check_raw_data", lambda: None)


def test_make_client_ollama_uses_host_and_checks_ready(monkeypatch):
    from src.clients.local import OllamaClient

    checked = []
    monkeypatch.setenv("OLLAMA_HOST", "http://box:1234")
    monkeypatch.setattr(OllamaClient, "check_ready", lambda self: checked.append(self.host))
    c = main.make_client(load_model("qwen3_8b"))
    assert isinstance(c, OllamaClient) and checked == ["http://box:1234"]


def test_golden_calls_get_repeated_runs(tmp_path, monkeypatch):
    calls = [transcript(call_id="g", split="golden"), transcript(call_id="d", split="dev")]
    _patch_run(monkeypatch, FakeClient(*[VALID_JSON] * 4), calls)
    main.main(["run", "--yes", "--golden-runs", "3", "--out-dir", str(tmp_path)])
    lines = [json.loads(l) for l in next(tmp_path.glob("*.jsonl")).read_text().splitlines()]
    assert [(l["call_id"], l["run_idx"]) for l in lines] == [("g", 0), ("g", 1), ("g", 2), ("d", 0)]


def test_matrix_runs_every_combination_then_evaluates(tmp_path, monkeypatch):
    combos, evaluated = [], []
    monkeypatch.setattr(main, "load_calls", lambda split: [transcript()])
    monkeypatch.setattr(main, "check_raw_data", lambda: None)
    monkeypatch.setattr(main, "make_client", lambda cfg: FakeClient())
    monkeypatch.setattr(main, "run_combo", lambda client, model, prompt, sampling, *a, **k: combos.append(
        (model.name, prompt.version, sampling.name)))
    monkeypatch.setattr(main, "evaluate", lambda runs_dir, out_dir: evaluated.append(runs_dir))
    main.main(["matrix", "--yes", "--models", "gpt4o_mini", "qwen3_8b", "--prompts", "v1", "--samplings", "deterministic", "low",
               "--out-dir", str(tmp_path)])
    assert combos == [("gpt4o_mini", "v1", "deterministic"), ("gpt4o_mini", "v1", "low"),
                      ("qwen3_8b", "v1", "deterministic"), ("qwen3_8b", "v1", "low")]
    assert evaluated == [tmp_path]


def test_matrix_default_prompts_are_v1_v2(monkeypatch):
    seen = {}
    monkeypatch.setattr(main, "matrix", lambda args: seen.update(prompts=args.prompts))
    main.main(["matrix"])
    assert seen["prompts"] == ["v1", "v2"]
