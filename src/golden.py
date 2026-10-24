"""Golden-set hand labels (data/golden/golden_<version>.jsonl), keyed by call ID (spec §3)."""

import json
from pathlib import Path

from src.dataset import read_manifest
from src.schema import CallQARecord


def load_golden(
    path: Path = Path("data/golden/golden_v1.jsonl"), manifest: Path = Path("data/manifest.csv")
) -> dict[str, CallQARecord]:
    golden_ids = {r.call_id for r in read_manifest(manifest) if r.split == "golden"}
    labels: dict[str, CallQARecord] = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        call_id = entry["call_id"]
        if call_id in labels:
            raise ValueError(f"duplicate golden label for {call_id}")
        if call_id not in golden_ids:
            raise ValueError(f"{call_id} is not a golden call in {manifest}")
        labels[call_id] = CallQARecord.model_validate(entry["label"])
    return labels
