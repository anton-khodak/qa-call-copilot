"""Metrics per (model, prompt version, sampling) combination (spec §11).

Only the latest run file of each combination is scored. Golden accuracy is computed per run_idx
and the median across runs is reported; a failed record counts as wrong on every field.
"""

import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from src.dataset import read_manifest
from src.golden import load_golden_partial
from src.schema import CallQARecord

INFERRED = ["domain", "direction", "customer_intent", "outcome", "next_action"]
EXTRACTED = ["agent_handoff", "recording_disclosed", "disclaimer_before_benefits"]
GOLDEN_COLUMNS = (
    [f"acc_{f}" for f in INFERRED + EXTRACTED]
    + ["obj_precision", "obj_recall", "obj_f1", "obj_handled_acc", "acc_extracted", "acc_inferred",
       "golden_calls", "golden_runs"]
)
COLUMNS = [
    "model", "provider", "prompt_version", "sampling_name", "n_records", "n_calls",
    "valid_first_try_pct", "valid_after_repair_pct", "failed_pct",
    "latency_p50_ms", "latency_p95_ms", "cost_per_1k_usd", "domain_acc_all",
] + GOLDEN_COLUMNS

Combo = tuple[str, str, str]


def percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile."""
    s = sorted(values)
    return s[max(0, math.ceil(q / 100 * len(s)) - 1)]


def load_runs(runs_dir: Path) -> list[dict]:
    records = []
    for path in sorted(Path(runs_dir).glob("*.jsonl")):
        records += [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return records


def latest_per_combo(records: list[dict]) -> dict[Combo, list[dict]]:
    groups: dict[Combo, list[dict]] = defaultdict(list)
    for r in records:
        groups[(r["model"], r["prompt_version"], r["sampling_name"])].append(r)
    latest = {}
    for combo, rs in groups.items():
        run_id = max(r["run_id"] for r in rs)
        latest[combo] = [r for r in rs if r["run_id"] == run_id]
    return latest


def field_values(parsed: dict | None) -> dict:
    if parsed is None:
        return {}
    c = parsed["compliance"]
    return {
        **{f: parsed[f] for f in INFERRED},
        "agent_handoff": parsed["agent_handoff"],
        "recording_disclosed": c["recording_disclosed"]["value"],
        "disclaimer_before_benefits": c["disclaimer_before_benefits"]["value"],
    }


def objection_scores(pairs: list[tuple[list[dict] | None, list[dict]]]) -> tuple[float, float, float, float | None]:
    """Micro precision/recall/F1 on objection types, plus `handled` accuracy on matched types.
    A failed prediction (None) counts as predicting no objections."""
    tp = n_pred = n_gold = handled_ok = 0
    for pred, gold in pairs:
        p = {o["type"]: o["handled"] for o in pred or []}
        g = {o["type"]: o["handled"] for o in gold}
        matched = p.keys() & g.keys()
        tp += len(matched)
        n_pred += len(p)
        n_gold += len(g)
        handled_ok += sum(p[t] == g[t] for t in matched)
    precision = tp / n_pred if n_pred else float(n_gold == 0)
    recall = tp / n_gold if n_gold else float(n_pred == 0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1, (handled_ok / tp if tp else None)


def score_golden(records: list[dict], golden: dict[str, CallQARecord]) -> tuple[dict, list[dict]]:
    labels = {cid: g.model_dump(mode="json") for cid, g in golden.items()}
    by_run: dict[int, list[dict]] = defaultdict(list)
    for r in records:
        if r["call_id"] in labels:
            by_run[r["run_idx"]].append(r)
    if not by_run:
        return {c: None for c in GOLDEN_COLUMNS}, []

    per_run = defaultdict(list)
    class_hits: dict[tuple[str, str], list[bool]] = defaultdict(list)
    for rs in by_run.values():
        for f in INFERRED + EXTRACTED:
            hits = []
            for r in rs:
                gold_v = field_values(labels[r["call_id"]])[f]
                ok = field_values(r["parsed"]).get(f, object()) == gold_v
                hits.append(ok)
                if f in INFERRED:
                    class_hits[(f, gold_v)].append(ok)
            per_run[f"acc_{f}"].append(sum(hits) / len(hits))
        pairs = [((r["parsed"] or {}).get("objections"), labels[r["call_id"]]["objections"]) for r in rs]
        for name, v in zip(["obj_precision", "obj_recall", "obj_f1", "obj_handled_acc"], objection_scores(pairs)):
            if v is not None:
                per_run[name].append(v)

    out = {name: statistics.median(vs) if vs else None for name, vs in per_run.items()}
    out["acc_inferred"] = statistics.mean(out[f"acc_{f}"] for f in INFERRED)
    out["acc_extracted"] = statistics.mean([out[f"acc_{f}"] for f in EXTRACTED] + [out["obj_f1"]])
    out["golden_calls"] = len({r["call_id"] for rs in by_run.values() for r in rs})
    out["golden_runs"] = len(by_run)
    per_class = [
        {"field": f, "class": c, "n": len(h), "accuracy": sum(h) / len(h)} for (f, c), h in sorted(class_hits.items())
    ]
    return {c: out.get(c) for c in GOLDEN_COLUMNS}, per_class


def combo_metrics(records: list[dict], source_domains: dict[str, str], golden: dict[str, CallQARecord]) -> dict:
    n = len(records)
    status = defaultdict(int)
    for r in records:
        status[r["status"]] += 1
    first = [r for r in records if r["run_idx"] == 0]
    domain_ok = [
        r["status"] != "failed" and r["parsed"]["domain"] == source_domains.get(r["call_id"]) for r in first
    ]
    latencies = [r["latency_ms"] for r in records]
    golden_scores, _ = score_golden(records, golden)
    r0 = records[0]
    return {
        "model": r0["model"],
        "provider": r0["provider"],
        "prompt_version": r0["prompt_version"],
        "sampling_name": r0["sampling_name"],
        "n_records": n,
        "n_calls": len({r["call_id"] for r in records}),
        "valid_first_try_pct": 100 * status["valid_first_try"] / n,
        "valid_after_repair_pct": 100 * status["valid_after_repair"] / n,
        "failed_pct": 100 * status["failed"] / n,
        "latency_p50_ms": percentile(latencies, 50),
        "latency_p95_ms": percentile(latencies, 95),
        "cost_per_1k_usd": 1000 * statistics.mean(r["cost_usd"] for r in records),
        "domain_acc_all": sum(domain_ok) / len(domain_ok) if domain_ok else None,
        **golden_scores,
    }


def _fmt(v, digits=2) -> str:
    if v is None:
        return "–"
    return f"{v:.{digits}f}" if isinstance(v, float) else str(v)


def markdown_table(rows: list[dict]) -> str:
    head = ("| model | prompt | sampling | valid 1st try % | failed % | p50 s | p95 s | $ / 1k calls | "
            "domain acc (all) | extracted acc | inferred acc | objections F1 | golden runs |")
    lines = [head, "|" + "---|" * (head.count("|") - 1)]
    for r in rows:
        lines.append("| " + " | ".join([
            r["model"], r["prompt_version"], r["sampling_name"], _fmt(r["valid_first_try_pct"], 0),
            _fmt(r["failed_pct"], 0), _fmt(r["latency_p50_ms"] / 1000, 1), _fmt(r["latency_p95_ms"] / 1000, 1),
            _fmt(r["cost_per_1k_usd"], 3), _fmt(r["domain_acc_all"]), _fmt(r["acc_extracted"]),
            _fmt(r["acc_inferred"]), _fmt(r["obj_f1"]), _fmt(r["golden_runs"]),
        ]) + " |")
    return "\n".join(lines) + "\n"


def evaluate(
    runs_dir: Path = Path("results/runs"),
    out_dir: Path = Path("results"),
    golden_path: Path = Path("data/golden/golden_v1.jsonl"),
    manifest: Path = Path("data/manifest.csv"),
) -> list[dict]:
    source_domains = {r.call_id: r.domain for r in read_manifest(manifest)}
    golden, skipped = load_golden_partial(golden_path, manifest) if Path(golden_path).exists() else ({}, [])
    if skipped:
        print(f"{len(skipped)} of {len(golden) + len(skipped)} golden labels incomplete or invalid, not scored: "
              f"{', '.join(skipped)}")
    rows, per_class_rows = [], []
    for combo, records in sorted(latest_per_combo(load_runs(runs_dir)).items()):
        rows.append(combo_metrics(records, source_domains, golden))
        per_class_rows += [{"model": combo[0], "prompt_version": combo[1], "sampling_name": combo[2], **c}
                           for c in score_golden(records, golden)[1]]

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "metrics.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    with open(out_dir / "per_class.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["model", "prompt_version", "sampling_name", "field", "class", "n", "accuracy"])
        w.writeheader()
        w.writerows(per_class_rows)
    table = markdown_table(rows)
    note = "" if golden else "\nGolden labels missing: accuracy columns are empty until data/golden/golden_v1.jsonl is filled.\n"
    (out_dir / "metrics.md").write_text(table + note)
    print(table + note)
    return rows
