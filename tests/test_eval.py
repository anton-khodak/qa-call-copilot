import copy
import csv
import json

import pytest

from src.eval import (
    combo_metrics,
    evaluate,
    field_table,
    latest_per_combo,
    markdown_table,
    objection_scores,
    percentile,
    score_golden,
)
from src.schema import CallQARecord
from tests.test_schema import VALID


def rec(call_id="a", run_idx=0, status="valid_first_try", parsed=None, latency=100, cost=0.001,
        run_id="r1", model="m", sampling="deterministic", split="golden"):
    parsed = copy.deepcopy(VALID) if parsed is None and status != "failed" else parsed
    return {"run_id": run_id, "call_id": call_id, "split": split, "model": model, "provider": "p",
            "prompt_version": "v1", "sampling_name": sampling, "run_idx": run_idx, "status": status,
            "latency_ms": latency, "cost_usd": cost, "parsed": parsed}


def gold(**over):
    d = copy.deepcopy(VALID)
    d.update(over)
    return CallQARecord.model_validate(d)


def test_percentile_nearest_rank():
    v = list(range(1, 101))
    assert percentile(v, 50) == 50 and percentile(v, 95) == 95 and percentile([7], 95) == 7


def test_latest_run_per_combo_only():
    rs = [rec(run_id="20261024T1"), rec(run_id="20261024T2"), rec(run_id="20261024T1", sampling="low")]
    groups = latest_per_combo(rs)
    assert {k: {r["run_id"] for r in v} for k, v in groups.items()} == {
        ("m", "v1", "deterministic"): {"20261024T2"}, ("m", "v1", "low"): {"20261024T1"}}


def test_objection_scores():
    pred = [{"type": "price", "handled": True}, {"type": "timing", "handled": False}]
    gold_ = [{"type": "price", "handled": False}, {"type": "already_covered", "handled": True}]
    p, r, f1, handled = objection_scores([(pred, gold_)])
    assert (p, r, f1, handled) == (0.5, 0.5, 0.5, 0.0)


def test_objection_scores_failed_prediction_counts_as_empty():
    p, r, f1, handled = objection_scores([(None, [{"type": "price", "handled": True}])])
    assert r == 0.0 and f1 == 0.0 and handled is None


def test_objection_scores_both_empty_is_perfect():
    assert objection_scores([([], [])])[:3] == (1.0, 1.0, 1.0)


def test_score_golden_median_over_runs_and_failed_is_wrong():
    golden = {"a": gold(), "b": gold(outcome="sale")}
    rs = [
        rec("a", 0), rec("b", 0),                      # run 0: outcome 1/2
        rec("a", 1), rec("b", 1, status="failed"),     # run 1: outcome 1/2 (failed counts wrong)
        rec("a", 2), rec("b", 2, parsed={**VALID, "outcome": "sale"}),  # run 2: 2/2
    ]
    s, per_class = score_golden(rs, golden)
    assert s["acc_outcome"] == 0.5 and s["acc_call_type"] == 1.0 and s["golden_runs"] == 3
    assert s["acc_inferred"] == pytest.approx((1 + 1 + 0.5) / 3)
    sale = next(c for c in per_class if c["field"] == "outcome" and c["class"] == "sale")
    assert (sale["n"], sale["accuracy"]) == (3, pytest.approx(1 / 3))


def test_score_golden_ignores_calls_without_labels():
    s, _ = score_golden([rec("a"), rec("zzz", parsed={**VALID, "call_type": "other"})], {"a": gold()})
    assert s["acc_call_type"] == 1.0


def test_combo_metrics():
    rs = [rec("a", latency=100, cost=0.002), rec("b", status="failed", latency=300, cost=0.0),
          rec("a", 1, latency=200, cost=0.001)]
    m = combo_metrics(rs, {"a": "plan_sales", "b": "plan_sales"}, {})
    assert (m["n_records"], m["n_calls"]) == (3, 2)
    assert m["valid_first_try_pct"] == pytest.approx(200 / 3) and m["failed_pct"] == pytest.approx(100 / 3)
    assert (m["latency_p50_ms"], m["latency_p95_ms"]) == (200, 300)
    assert m["cost_per_1k_usd"] == pytest.approx(1.0)
    assert m["call_type_acc_all"] == 0.5  # run_idx 0 only; failed b counts wrong
    assert m["acc_call_type"] is None  # no golden labels yet


def test_evaluate_writes_outputs(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "r1.jsonl").write_text(json.dumps(rec("a")) + "\n")
    (runs / "r2.jsonl.partial").write_text(json.dumps(rec("a", model="aborted")) + "\n")
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("call_id,segment,zip_name,member,file_size,audio_duration,word_count,split\n"
                        "a,outbound_plan,z,m,1,,,golden\n")
    golden = tmp_path / "golden.jsonl"
    golden.write_text(json.dumps({"call_id": "a", "label": VALID}) + "\n")

    rows = evaluate(runs, tmp_path, golden_path=golden, manifest=manifest)

    assert [r["model"] for r in rows] == ["m"] and rows[0]["acc_outcome"] == 1.0
    with open(tmp_path / "metrics.csv") as f:
        assert next(csv.DictReader(f))["model"] == "m"
    assert (tmp_path / "per_class.csv").exists()
    assert "| m |" in (tmp_path / "metrics.md").read_text()


def test_evaluate_skips_incomplete_golden_labels(tmp_path, capsys):
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "r1.jsonl").write_text(json.dumps(rec("a")) + json.dumps(rec("b")).join(["\n", "\n"]))
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("call_id,segment,zip_name,member,file_size,audio_duration,word_count,split\n"
                        "a,outbound_plan,z,m,1,,,golden\nb,outbound_plan,z,m,1,,,golden\n")
    golden = tmp_path / "golden.jsonl"
    blank = {**VALID, "outcome": "", "agent_handoff": ""}  # labelling in progress
    golden.write_text(json.dumps({"call_id": "a", "label": VALID}) + "\n" + json.dumps({"call_id": "b", "label": blank}) + "\n")

    rows = evaluate(runs, tmp_path, golden_path=golden, manifest=manifest)

    assert rows[0]["golden_calls"] == 1 and rows[0]["acc_outcome"] == 1.0
    assert "1 of 2 golden labels incomplete" in capsys.readouterr().out


def _row(**over):
    m = combo_metrics([rec("a")], {"a": "plan_sales"}, {"a": gold()})
    return {**m, **over}


def test_markdown_table_has_repair_column():
    t = markdown_table([_row(valid_after_repair_pct=5.0)])
    assert "repaired %" in t.splitlines()[0] and "| 5 |" in t.splitlines()[2]


def test_field_table_lists_every_field():
    head = field_table([_row()]).splitlines()[0]
    for col in ["call_type", "direction", "outcome", "agent_handoff", "recording_disclosed",
                "obj P", "obj R", "obj F1", "handled"]:
        assert col in head, col
    assert "disclaimer" not in head
    assert "| 1.00 |" in field_table([_row()]).splitlines()[2]


def test_evaluate_writes_both_tables(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "r1.jsonl").write_text(json.dumps(rec("a")) + "\n")
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("call_id,segment,zip_name,member,file_size,audio_duration,word_count,split\n"
                        "a,outbound_plan,z,m,1,,,golden\n")
    golden = tmp_path / "golden.jsonl"
    golden.write_text(json.dumps({"call_id": "a", "label": VALID}) + "\n")
    evaluate(runs, tmp_path, golden_path=golden, manifest=manifest)
    md = (tmp_path / "metrics.md").read_text()
    assert "repaired %" in md and "recording_disclosed" in md
