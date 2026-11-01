"""Golden-set disagreements for the error analysis in REPORT.md (spec §12).

One CSV row per (combination, call, run, field) where the latest run disagrees with the golden label.
A failed record is one row with field `*`; objections are one row when the predicted and golden type
sets differ.
"""

import csv
from pathlib import Path

from src.eval import EXTRACTED, INFERRED, field_values, latest_per_combo, load_runs
from src.golden import load_golden_partial
from src.schema import CallQARecord

ERROR_COLUMNS = ["model", "prompt_version", "sampling_name", "call_id", "run_idx", "field", "gold", "predicted",
                 "evidence"]
COMPLIANCE = ("recording_disclosed",)


def _types(objections: list[dict]) -> str:
    return ",".join(sorted({o["type"] for o in objections}))


def golden_errors(records: list[dict], golden: dict[str, CallQARecord]) -> list[dict]:
    rows = []
    for r in records:
        if r["call_id"] not in golden:
            continue
        label = golden[r["call_id"]].model_dump(mode="json")
        base = {k: r[k] for k in ("model", "prompt_version", "sampling_name", "call_id", "run_idx")}
        pred = r["parsed"]
        if pred is None:
            rows.append({**base, "field": "*", "gold": None, "predicted": "failed", "evidence": None})
            continue
        gold_v, pred_v = field_values(label), field_values(pred)
        for f in INFERRED + EXTRACTED:
            if pred_v[f] != gold_v[f]:
                evidence = pred["compliance"][f]["evidence"] if f in COMPLIANCE else None
                rows.append({**base, "field": f, "gold": gold_v[f], "predicted": pred_v[f], "evidence": evidence})
        if _types(pred["objections"]) != _types(label["objections"]):
            rows.append({**base, "field": "objections", "gold": _types(label["objections"]),
                         "predicted": _types(pred["objections"]), "evidence": None})
    return rows


def write_errors(
    runs_dir: Path = Path("results/runs"),
    out: Path = Path("results/golden_errors.csv"),
    golden_path: Path = Path("data/golden/golden_v3.jsonl"),
    manifest: Path = Path("data/manifest.csv"),
) -> int:
    golden, _ = load_golden_partial(golden_path, manifest)
    rows = []
    for _, records in sorted(latest_per_combo(load_runs(runs_dir)).items()):
        rows += golden_errors(records, golden)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ERROR_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} golden disagreements written to {out}")
    return len(rows)
