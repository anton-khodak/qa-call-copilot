"""Local labelling UI for the golden set. Run `make label` and open http://127.0.0.1:8765.

Shows each golden transcript next to a form built from the CallQARecord schema (field and option
help come from the Field descriptions, rules from data/golden/LABELING.md). Every save rewrites
that call's line in golden_v2.jsonl; incomplete labels are saved as drafts and reported as errors."""

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


def save_label(path: Path, call_id: str, label: dict) -> list[dict]:
    """Replace (or append) call_id's line and write the file atomically. Returns validation errors."""
    entries = read_entries(path)
    for entry in entries:
        if entry["call_id"] == call_id:
            entry["label"] = label
            break
    else:
        entries.append({"call_id": call_id, "label": label})
    tmp = path.with_suffix(".jsonl.tmp")
    tmp.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries))
    os.replace(tmp, path)
    return validate(label)


def state() -> dict:
    labels = {e["call_id"]: e["label"] for e in read_entries(GOLDEN)}
    calls = []
    for row in read_manifest(MANIFEST):
        if row.split != "golden":
            continue
        label = labels.get(row.call_id, {})
        calls.append(
            {
                "call_id": row.call_id,
                "text": load_transcript(row).text,
                "label": label,
                "errors": validate(label),
            }
        )
    return {"schema": strict_json_schema(), "rules": RULES.read_text(), "calls": calls}


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
        if self.path != "/api/label":
            return self._json({"error": "not found"}, 404)
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        golden_ids = {r.call_id for r in read_manifest(MANIFEST) if r.split == "golden"}
        if body.get("call_id") not in golden_ids:
            return self._json({"error": "not a golden call"}, 400)
        self._json({"errors": save_label(GOLDEN, body["call_id"], body["label"])})

    def log_message(self, *args):
        pass


def main(port: int = 8765):
    print(f"Labelling {GOLDEN} at http://127.0.0.1:{port}  (Ctrl+C to stop)")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
