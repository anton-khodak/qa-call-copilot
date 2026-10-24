"""Call selection, manifest I/O and transcript loading (spec §3). Reused by later stages."""

import csv
import json
import random
from collections.abc import Callable
from dataclasses import asdict, dataclass, fields
from pathlib import Path

REPO_ID = "AIxBlock/92k-real-world-call-center-scripts-english"
# Medicare only, three call types (segments): segment -> (source zip, expected call_type).
# Source zips are noisy (medicare_inbound.zip is mostly vet clinics), so every selected call
# must mention Medicare; see data/README.md.
SEGMENTS = {
    "inbound_plan": ("automotive_and_healthcare_insurance_inbound.zip", "plan_sales"),
    "outbound_plan": ("insurance_outbound.zip", "plan_sales"),
    "outbound_equipment": ("medical_equipment_outbound.zip", "medical_equipment"),
}
GOLDEN_COUNTS = {"inbound_plan": 4, "outbound_plan": 3, "outbound_equipment": 3}
SUFFIX = "_transcript.json"


@dataclass
class ManifestRow:
    call_id: str
    segment: str
    zip_name: str
    member: str
    file_size: int
    audio_duration: float | None
    word_count: int | None
    split: str


@dataclass
class Transcript:
    call_id: str
    segment: str
    split: str
    text: str
    audio_duration: float | None
    words: list[dict]

    @property
    def source_call_type(self) -> str:
        return SEGMENTS[self.segment][1]


def mentions_medicare(raw: bytes) -> bool:
    return "medicare" in (json.loads(raw).get("text") or "").lower()


def call_id_from_member(member: str) -> str | None:
    if member.startswith("__MACOSX") or not member.endswith(SUFFIX):
        return None
    name = member.rsplit("/", 1)[-1]
    if name.startswith("._"):
        return None
    return name[: -len(SUFFIX)]


SIZE_BINS = (0.0, 0.05, 0.35, 0.65, 1.0)


def select_members(
    members: list[tuple[str, int]], n: int = 12, seed: int = 42, accept: Callable[[str], bool] = lambda m: True
) -> list[tuple[str, int]]:
    """Pick n // 4 accepted members from each file-size bin, in seeded random order. File size is
    a proxy for call length; the first bin is the bottom 5%, so a few short/broken calls are
    always included. 0-byte files are not transcripts and are skipped."""
    rng = random.Random(seed)
    ordered = sorted((m for m in members if m[1] > 0), key=lambda m: (m[1], m[0]))
    picked = []
    for lo, hi in zip(SIZE_BINS, SIZE_BINS[1:]):
        bin_ = ordered[round(lo * len(ordered)) : round(hi * len(ordered))]
        rng.shuffle(bin_)
        chosen = list(_take(bin_, accept, n // 4))
        if len(chosen) < n // 4:
            raise ValueError(f"only {len(chosen)} accepted members in size band {lo:.0%}-{hi:.0%}")
        picked += chosen
    return picked


def _take(items, accept, k):
    for m in items:
        if k == 0:
            return
        if accept(m[0]):
            k -= 1
            yield m


def assign_splits(
    rows: list[ManifestRow], golden_counts: dict[str, int] = GOLDEN_COUNTS, seed: int = 42
) -> list[ManifestRow]:
    rng = random.Random(seed)
    golden = set()
    for segment, k in golden_counts.items():
        ids = sorted(r.call_id for r in rows if r.segment == segment)
        golden.update(rng.sample(ids, k))
    for r in rows:
        r.split = "golden" if r.call_id in golden else "dev"
    return rows


def _parse(field_type, value: str):
    if value == "":
        return None if "None" in str(field_type) else ""
    if "int" in str(field_type):
        return int(value)
    if "float" in str(field_type):
        return float(value)
    return value


def read_manifest(path: Path) -> list[ManifestRow]:
    types = {f.name: f.type for f in fields(ManifestRow)}
    with open(path, newline="") as f:
        return [ManifestRow(**{k: _parse(types[k], v) for k, v in row.items()}) for row in csv.DictReader(f)]


def write_manifest(path: Path, rows: list[ManifestRow]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[fl.name for fl in fields(ManifestRow)])
        w.writeheader()
        for r in rows:
            w.writerow({k: "" if v is None else v for k, v in asdict(r).items()})


def raw_path(row: ManifestRow, raw_dir: Path = Path("data/raw")) -> Path:
    return Path(raw_dir) / row.segment / f"{row.call_id}.json"


def load_transcript(row: ManifestRow, raw_dir: Path = Path("data/raw")) -> Transcript:
    d = json.loads(raw_path(row, raw_dir).read_text())
    return Transcript(
        call_id=row.call_id,
        segment=row.segment,
        split=row.split,
        text=d.get("text") or "",
        audio_duration=d.get("audio_duration"),
        words=d.get("words") or [],
    )


def load_calls(
    split: str = "all", manifest: Path = Path("data/manifest.csv"), raw_dir: Path = Path("data/raw")
) -> list[Transcript]:
    rows = read_manifest(manifest)
    return [load_transcript(r, raw_dir) for r in rows if split == "all" or r.split == split]
