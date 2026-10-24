"""Local labelling UI for the golden set. Run `make label` and open http://127.0.0.1:8765.

Shows each golden transcript next to a form built from the CallQARecord schema (field and option
help come from the Field descriptions, rules from data/golden/LABELING.md). Every save rewrites
that call's line in golden_v2.jsonl; incomplete labels are saved as drafts and reported as errors.

Model annotators' labels (ANNOTATORS: same format plus a per-field "reasoning" dict) are compared
with golden; fields where any of them disagrees are listed per call with each one's value and
reasoning. A pick ("keep mine" / "take <annotator>") is applied to golden_v2.jsonl and recorded in
review_v2.json with every value at decision time. A decision stays settled while each annotator's
value is the one it saw; an annotator added later that disagrees reopens the field."""

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pydantic

from src.dataset import load_transcript, read_manifest
from src.schema import CallQARecord, strict_json_schema

GOLDEN = Path("data/golden/golden_v2.jsonl")
MANIFEST = Path("data/manifest.csv")
RULES = Path("data/golden/LABELING.md")
ANNOTATORS = {
    "opus": Path("data/golden/opus_v2.jsonl"),  # Claude Opus 5.5, labelled blind in Claude Code
    "astra": Path("data/golden/astra_v2.jsonl"),  # openai/gpt-6-astra via OpenRouter, same rules + transcript
}
REVIEW = Path("data/golden/review_v2.json")
# scored fields (LABELING.md); for compliance checks only .value is compared, evidence is not scored
COMPARED = [
    "call_type",
    "direction",
    "outcome",
    "objections",
    "compliance.recording_disclosed",
    "compliance.disclaimer_before_benefits",
    "agent_handoff",
]
PAGE = Path(__file__).with_name("label_app.html")


def validate(label: dict) -> list[dict]:
    try:
        CallQARecord.model_validate(label)
    except pydantic.ValidationError as e:
        return [{"loc": ".".join(str(p) for p in err["loc"]), "msg": err["msg"]} for err in e.errors()]
    return []


def read_entries(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_entries(path: Path, entries: list[dict]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries))
    os.replace(tmp, path)


def save_label(path: Path, call_id: str, label: dict) -> list[dict]:
    """Replace (or append) call_id's line and write the file atomically. Returns validation errors."""
    entries = read_entries(path)
    for entry in entries:
        if entry["call_id"] == call_id:
            entry["label"] = label
            break
    else:
        entries.append({"call_id": call_id, "label": label})
    write_entries(path, entries)
    return validate(label)


def get_field(label: dict, field: str):
    for part in field.split("."):
        label = label.get(part, {}) if isinstance(label, dict) else {}
    return label


def set_field(label: dict, field: str, value) -> None:
    *parents, last = field.split(".")
    for part in parents:
        label = label.setdefault(part, {})
    label[last] = value


def comparable(field: str, value):
    if field.startswith("compliance."):
        return value.get("value") if isinstance(value, dict) else value
    if field == "objections" and isinstance(value, list):
        return sorted((o.get("type"), o.get("handled")) for o in value)
    return value


def same(field: str, a, b) -> bool:
    return comparable(field, a) == comparable(field, b)


def settled(field: str, record: dict | None, mine, theirs: dict) -> bool:
    """A decision still covers the field if every annotator's current value is the one recorded, or
    (for an annotator the decision predates) agrees with the current golden value."""
    if not record:
        return False
    return all(
        same(field, record[name], value) if name in record else same(field, mine, value)
        for name, value in theirs.items()
    )


def conflicts(mine: dict, theirs: dict[str, dict], decided: dict) -> list[dict]:
    """Per scored field: open if any annotator disagrees with golden and no decision covers it;
    resolved (shown with the values at decision time) if a decision does."""
    out = []
    for field in COMPARED:
        mv = get_field(mine, field)
        values = {name: get_field(label, field) for name, label in theirs.items()}
        record = decided.get(field)
        if settled(field, record, mv, values):
            out.append({"field": field, "human": record["human"], "choice": record["choice"],
                        "values": {name: record.get(name, mv) for name in values}})
        elif any(not same(field, mv, v) for v in values.values()):
            out.append({"field": field, "human": mv, "choice": None, "values": values})
    return out


def read_review(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def annotator_entries(annotators: dict[str, Path]) -> dict[str, dict[str, dict]]:
    """{name: {call_id: entry}} for the annotators whose file exists."""
    return {name: {e["call_id"]: e for e in read_entries(p)} for name, p in annotators.items() if p.exists()}


def resolve(call_id: str, field: str, choice: str, golden: Path = GOLDEN,
            annotators: dict[str, Path] = ANNOTATORS, review: Path = REVIEW) -> list[dict]:
    """Apply choice ("human" or an annotator name) for one field to golden and record it in review.
    A decision that no longer covers the field is moved to the record's "history". Returns errors."""
    others = annotator_entries(annotators)
    if field not in COMPARED or choice not in ("human", *others):
        raise ValueError(f"bad field/choice: {field}/{choice}")
    entries = read_entries(golden)
    entry = next(e for e in entries if e["call_id"] == call_id)
    mv = get_field(entry["label"], field)
    values = {name: get_field(by_id[call_id]["label"], field) for name, by_id in others.items() if call_id in by_id}
    decisions = read_review(review)
    old = decisions.setdefault(call_id, {}).get(field)
    if settled(field, old, mv, values):
        record = {**old, **{n: old.get(n, mv) for n in values}}
    else:
        history = (old or {}).pop("history", []) + ([old] if old else [])
        record = {"human": mv, **values, **({"history": history} if history else {})}
    record["choice"] = choice
    decisions[call_id][field] = record
    set_field(entry["label"], field, record[choice])
    write_entries(golden, entries)
    tmp = review.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(decisions, indent=1, ensure_ascii=False) + "\n")
    os.replace(tmp, review)
    return validate(entry["label"])


def state() -> dict:
    labels = {e["call_id"]: e["label"] for e in read_entries(GOLDEN)}
    others = annotator_entries(ANNOTATORS)
    decisions = read_review(REVIEW)
    calls = []
    for row in read_manifest(MANIFEST):
        if row.split != "golden":
            continue
        label = labels.get(row.call_id, {})
        theirs = {name: by_id[row.call_id] for name, by_id in others.items() if row.call_id in by_id}
        calls.append(
            {
                "call_id": row.call_id,
                "text": load_transcript(row).text,
                "label": label,
                "errors": validate(label),
                "conflicts": conflicts(label, {n: e["label"] for n, e in theirs.items()},
                                       decisions.get(row.call_id, {})),
                "reasoning": {n: e.get("reasoning", {}) for n, e in theirs.items()},
            }
        )
    return {"schema": strict_json_schema(), "rules": RULES.read_text(), "annotators": list(others), "calls": calls}


class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, ctype: str, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status: int = 200):
        self._send(json.dumps(obj).encode(), "application/json", status)

    def do_GET(self):
        if self.path == "/":
            self._send(PAGE.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/state":
            self._json(state())
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path not in ("/api/label", "/api/resolve"):
            return self._json({"error": "not found"}, 404)
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        golden_ids = {r.call_id for r in read_manifest(MANIFEST) if r.split == "golden"}
        if body.get("call_id") not in golden_ids:
            return self._json({"error": "not a golden call"}, 400)
        if self.path == "/api/label":
            return self._json({"errors": save_label(GOLDEN, body["call_id"], body["label"])})
        try:
            errors = resolve(body["call_id"], body["field"], body["choice"])
        except ValueError as e:
            return self._json({"error": str(e)}, 400)
        call = next(c for c in state()["calls"] if c["call_id"] == body["call_id"])
        self._json({"errors": errors, "label": call["label"], "conflicts": call["conflicts"]})

    def log_message(self, *args):
        pass


def main(port: int = 8765):
    print(f"Labelling {GOLDEN} at http://127.0.0.1:{port}  (Ctrl+C to stop)")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
