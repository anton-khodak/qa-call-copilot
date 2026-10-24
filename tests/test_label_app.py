import json

from src import label_app
from src.label_app import save_label
from tests.test_schema import VALID


def test_save_label_replaces_only_that_line(tmp_path):
    p = tmp_path / "golden.jsonl"
    p.write_text(json.dumps({"call_id": "a", "label": {}}) + "\n" + json.dumps({"call_id": "b", "label": {}}) + "\n")
    assert save_label(p, "b", VALID) == []
    lines = [json.loads(l) for l in p.read_text().splitlines()]
    assert [l["call_id"] for l in lines] == ["a", "b"]
    assert lines[0]["label"] == {} and lines[1]["label"] == VALID


def test_save_label_keeps_draft_and_reports_errors(tmp_path):
    p = tmp_path / "golden.jsonl"
    draft = {**VALID, "call_type": ""}
    errors = save_label(p, "a", draft)
    assert [e["loc"] for e in errors] == ["call_type"]
    assert json.loads(p.read_text())["label"] == draft


def test_labels_go_to_golden_v2():
    assert label_app.GOLDEN.name == "golden_v2.jsonl"
