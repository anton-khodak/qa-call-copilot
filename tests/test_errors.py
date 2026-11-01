import copy
import csv
import json

from src.errors import ERROR_COLUMNS, golden_errors, write_errors
from tests.test_eval import gold, rec
from tests.test_schema import VALID


def test_golden_errors_lists_only_mismatches():
    pred = copy.deepcopy(VALID)
    pred["direction"] = "unknown" if VALID["direction"] != "unknown" else "inbound"
    rows = golden_errors([rec("a", parsed=pred), rec("b")], {"a": gold(), "b": gold()})
    assert [(r["call_id"], r["field"]) for r in rows] == [("a", "direction")]
    assert rows[0]["gold"] == VALID["direction"] and rows[0]["predicted"] == pred["direction"]
    assert (rows[0]["model"], rows[0]["prompt_version"], rows[0]["sampling_name"], rows[0]["run_idx"]) == (
        "m", "v1", "deterministic", 0)


def test_calls_without_golden_label_are_ignored():
    pred = {**copy.deepcopy(VALID), "outcome": "other"}
    assert golden_errors([rec("dev1", parsed=pred, split="dev")], {"a": gold()}) == []


def test_failed_record_is_one_row_with_predicted_failed():
    rows = golden_errors([rec("a", status="failed")], {"a": gold()})
    assert [(r["field"], r["predicted"]) for r in rows] == [("*", "failed")]


def test_evidence_is_predicted_quote_for_compliance_fields():
    pred = copy.deepcopy(VALID)
    pred["compliance"]["recording_disclosed"] = {"value": False, "evidence": "some quote"}
    g = copy.deepcopy(VALID)
    g["compliance"]["recording_disclosed"] = {"value": True, "evidence": None}
    rows = {r["field"]: r for r in golden_errors([rec("a", parsed=pred)], {"a": gold(**g)})}
    assert rows["recording_disclosed"]["predicted"] is False and rows["recording_disclosed"]["gold"] is True
    assert rows["recording_disclosed"]["evidence"] == "some quote"


def test_objection_mismatch_is_one_row_with_sorted_types():
    pred = {**copy.deepcopy(VALID), "objections": [{"type": "timing", "handled": True},
                                                  {"type": "price", "handled": False}]}
    g = {**copy.deepcopy(VALID), "objections": [{"type": "price", "handled": True}]}
    rows = golden_errors([rec("a", parsed=pred)], {"a": gold(**g)})
    obj = [r for r in rows if r["field"] == "objections"]
    assert len(obj) == 1 and obj[0]["predicted"] == "price,timing" and obj[0]["gold"] == "price"


def test_write_errors_empty_runs_writes_header_only(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    out = tmp_path / "golden_errors.csv"
    golden = tmp_path / "golden.jsonl"
    golden.write_text("")
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("call_id,segment,zip_name,member,file_size,audio_duration,word_count,split\n")
    assert write_errors(runs, out, golden_path=golden, manifest=manifest) == 0
    assert out.read_text().strip() == ",".join(ERROR_COLUMNS)


def test_write_errors_latest_combo_only(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    wrong = {**copy.deepcopy(VALID), "outcome": "other" if VALID["outcome"] != "other" else "sale"}
    (runs / "old.jsonl").write_text(json.dumps(rec("a", parsed=wrong, run_id="r0")) + "\n")
    (runs / "new.jsonl").write_text(json.dumps(rec("a", run_id="r1")) + "\n")
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("call_id,segment,zip_name,member,file_size,audio_duration,word_count,split\n"
                        "a,outbound_plan,z,m,1,,,golden\n")
    golden = tmp_path / "golden.jsonl"
    golden.write_text(json.dumps({"call_id": "a", "label": VALID}) + "\n")
    out = tmp_path / "golden_errors.csv"
    assert write_errors(runs, out, golden_path=golden, manifest=manifest) == 0
    with open(out) as f:
        assert list(csv.DictReader(f)) == []
