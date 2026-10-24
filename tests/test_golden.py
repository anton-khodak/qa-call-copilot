import json

import pydantic
import pytest

from src.dataset import ManifestRow, write_manifest
from src.golden import load_golden, load_golden_partial
from tests.test_schema import VALID


@pytest.fixture
def manifest(tmp_path):
    rows = [
        ManifestRow("g1", "medicare", "z.zip", "d/g1_transcript.json", 1, None, None, "golden"),
        ManifestRow("d1", "medicare", "z.zip", "d/d1_transcript.json", 1, None, None, "dev"),
    ]
    p = tmp_path / "manifest.csv"
    write_manifest(p, rows)
    return p


def _golden(tmp_path, *lines):
    p = tmp_path / "golden.jsonl"
    p.write_text("".join(json.dumps(l) + "\n" for l in lines))
    return p


def test_load_golden_valid(tmp_path, manifest):
    g = load_golden(_golden(tmp_path, {"call_id": "g1", "label": VALID}), manifest)
    assert list(g) == ["g1"] and g["g1"].domain.value == "medicare"


def test_duplicate_call_id_rejected(tmp_path, manifest):
    p = _golden(tmp_path, {"call_id": "g1", "label": VALID}, {"call_id": "g1", "label": VALID})
    with pytest.raises(ValueError, match="duplicate"):
        load_golden(p, manifest)


def test_non_golden_call_id_rejected(tmp_path, manifest):
    with pytest.raises(ValueError, match="d1"):
        load_golden(_golden(tmp_path, {"call_id": "d1", "label": VALID}), manifest)


def test_invalid_label_rejected(tmp_path, manifest):
    with pytest.raises(pydantic.ValidationError):
        load_golden(_golden(tmp_path, {"call_id": "g1", "label": {**VALID, "outcome": "maybe"}}), manifest)


def test_blank_lines_ignored(tmp_path, manifest):
    p = _golden(tmp_path, {"call_id": "g1", "label": VALID})
    p.write_text(p.read_text() + "\n")
    assert len(load_golden(p, manifest)) == 1


def test_non_strict_skips_invalid_labels(tmp_path, manifest):
    p = _golden(tmp_path, {"call_id": "g1", "label": {**VALID, "outcome": ""}})
    labels, skipped = load_golden_partial(p, manifest)
    assert labels == {} and skipped == ["g1"]
