import copy
import json

from src import label_app
from src.label_app import conflicts, resolve, save_label
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


def _setup(tmp_path, mine, **theirs):
    g = tmp_path / "golden.jsonl"
    g.write_text(json.dumps({"call_id": "a", "label": mine}) + "\n")
    annotators = {}
    for name, label in theirs.items():
        annotators[name] = tmp_path / f"{name}.jsonl"
        annotators[name].write_text(json.dumps({"call_id": "a", "label": label, "reasoning": {}}) + "\n")
    return g, annotators, tmp_path / "review.json"


def test_conflicts_ignore_evidence_and_objection_order():
    mine = copy.deepcopy(VALID)
    theirs = copy.deepcopy(VALID)
    theirs["compliance"]["recording_disclosed"]["evidence"] = "some other quote"
    theirs["objections"] = list(reversed(theirs["objections"]))
    assert conflicts(mine, {"opus": theirs}, {}) == []
    theirs["agent_handoff"] = not mine["agent_handoff"]
    assert [c["field"] for c in conflicts(mine, {"opus": theirs}, {})] == ["agent_handoff"]


def test_resolve_take_opus_then_revert(tmp_path):
    theirs = copy.deepcopy(VALID)
    theirs["compliance"]["recording_disclosed"] = {"value": None, "evidence": None}
    g, ann, r = _setup(tmp_path, VALID, opus=theirs)
    field = "compliance.recording_disclosed"
    assert resolve("a", field, "opus", g, ann, r) == []
    assert json.loads(g.read_text())["label"]["compliance"]["recording_disclosed"] == {"value": None, "evidence": None}
    rec = json.loads(r.read_text())["a"][field]
    assert rec["choice"] == "opus" and rec["human"] == VALID["compliance"]["recording_disclosed"]
    resolve("a", field, "human", g, ann, r)
    assert json.loads(g.read_text())["label"] == VALID
    decided = json.loads(r.read_text())["a"]
    assert [c["choice"] for c in conflicts(VALID, {"opus": theirs}, decided)] == ["human"]


def test_new_annotator_reopens_only_fields_it_disputes(tmp_path):
    opus = {**copy.deepcopy(VALID), "agent_handoff": not VALID["agent_handoff"]}
    g, ann, r = _setup(tmp_path, VALID, opus=opus)
    resolve("a", "agent_handoff", "human", g, ann, r)
    # astra agrees with the settled handoff value but disputes direction
    astra = {**copy.deepcopy(VALID), "direction": "unknown" if VALID["direction"] != "unknown" else "inbound"}
    ann["astra"] = tmp_path / "astra.jsonl"
    ann["astra"].write_text(json.dumps({"call_id": "a", "label": astra, "reasoning": {}}) + "\n")
    decided = json.loads(r.read_text())["a"]
    got = {c["field"]: c["choice"] for c in conflicts(VALID, {"opus": opus, "astra": astra}, decided)}
    assert got == {"agent_handoff": "human", "direction": None}
    # a later astra that disputes the settled field reopens it, keeping the old decision as history
    astra["agent_handoff"] = opus["agent_handoff"]
    ann["astra"].write_text(json.dumps({"call_id": "a", "label": astra, "reasoning": {}}) + "\n")
    assert {c["field"]: c["choice"] for c in conflicts(VALID, {"opus": opus, "astra": astra}, decided)}["agent_handoff"] is None
    resolve("a", "agent_handoff", "astra", g, ann, r)
    rec = json.loads(r.read_text())["a"]["agent_handoff"]
    assert rec["choice"] == "astra" and rec["history"][0]["choice"] == "human"
    assert json.loads(g.read_text())["label"]["agent_handoff"] == opus["agent_handoff"]
