"""Golden-set hand labels (data/golden/golden.jsonl), keyed by call ID (spec §3)."""

import json
from pathlib import Path

import pydantic

from src.dataset import read_manifest
from src.schema import CallQARecord


def load_golden(
    path: Path = Path("data/golden/golden.jsonl"), manifest: Path = Path("data/manifest.csv")
) -> dict[str, CallQARecord]:
    labels, _ = _load(path, manifest, strict=True)
    return labels


def load_golden_partial(
    path: Path = Path("data/golden/golden.jsonl"), manifest: Path = Path("data/manifest.csv")
) -> tuple[dict[str, CallQARecord], list[str]]:
    """Like load_golden, but skips labels that don't validate yet (labelling in progress).
    Returns (valid labels, skipped call IDs)."""
    return _load(path, manifest, strict=False)


def _load(path: Path, manifest: Path, strict: bool) -> tuple[dict[str, CallQARecord], list[str]]:
    golden_ids = {r.call_id for r in read_manifest(manifest) if r.split == "golden"}
    labels: dict[str, CallQARecord] = {}
    skipped: list[str] = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        call_id = entry["call_id"]
        if call_id in labels:
            raise ValueError(f"duplicate golden label for {call_id}")
        if call_id not in golden_ids:
            raise ValueError(f"{call_id} is not a golden call in {manifest}")
        try:
            labels[call_id] = CallQARecord.model_validate(entry["label"])
        except pydantic.ValidationError:
            if strict:
                raise
            skipped.append(call_id)
    return labels, skipped
