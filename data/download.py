"""Fetch the selected calls from the CallCenterEN dataset (spec §3).

With a committed data/manifest.csv, fetches exactly the listed calls. Without one (or with
--reselect), selects calls with a fixed seed and writes the manifest. Zips are read with HTTP
range requests, so only the central directory and the chosen members are downloaded.
"""

import argparse
import json
import os
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

from src.dataset import (  # noqa: E402
    REPO_ID,
    SEGMENTS,
    ManifestRow,
    assign_splits,
    call_id_from_member,
    mentions_medicare,
    raw_path,
    read_manifest,
    select_members,
    write_manifest,
)

PER_SEGMENT = 12
SEED = 42


def open_zip(zip_name: str) -> zipfile.ZipFile:
    from huggingface_hub import HfFileSystem

    fs = HfFileSystem(token=os.getenv("HF_TOKEN") or None)
    return zipfile.ZipFile(fs.open(f"datasets/{REPO_ID}/{zip_name}", "rb"))


def _extract(zf: zipfile.ZipFile, row: ManifestRow, raw_dir: Path) -> dict:
    dest = raw_path(row, raw_dir)
    if dest.exists():
        return json.loads(dest.read_text())
    data = zf.read(row.member)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return json.loads(data)


def fetch_listed(rows: list[ManifestRow], raw_dir: Path) -> None:
    for zip_name in sorted({r.zip_name for r in rows}):
        todo = [r for r in rows if r.zip_name == zip_name and not raw_path(r, raw_dir).exists()]
        if not todo:
            continue
        zf = open_zip(zip_name)
        for r in todo:
            _extract(zf, r, raw_dir)
        print(f"{zip_name}: fetched {len(todo)}")


def reselect(raw_dir: Path) -> list[ManifestRow]:
    rows = []
    for segment, (zip_name, _) in SEGMENTS.items():
        zf = open_zip(zip_name)
        members = [(i.filename, i.file_size) for i in zf.infolist() if call_id_from_member(i.filename)]
        read = []

        def accept(member: str) -> bool:
            read.append(member)
            return mentions_medicare(zf.read(member))

        chosen = select_members(members, PER_SEGMENT, SEED, accept=accept)
        for member, size in chosen:
            row = ManifestRow(call_id_from_member(member), segment, zip_name, member, size, None, None, "")
            d = _extract(zf, row, raw_dir)
            row.audio_duration = d.get("audio_duration")
            row.word_count = len(d.get("words") or [])
            rows.append(row)
        print(f"{segment}: {len(members)} available, {len(read)} read, {len(chosen)} mention Medicare and selected")
    return assign_splits(rows)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reselect", action="store_true", help="ignore the existing manifest and select anew")
    p.add_argument("--manifest", type=Path, default=Path("data/manifest.csv"))
    p.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    args = p.parse_args(argv)
    load_dotenv()

    if args.manifest.exists() and not args.reselect:
        rows = read_manifest(args.manifest)
        fetch_listed(rows, args.raw_dir)
    else:
        rows = reselect(args.raw_dir)
        write_manifest(args.manifest, rows)
    golden = sum(r.split == "golden" for r in rows)
    print(f"{len(rows)} calls in manifest ({golden} golden, {len(rows) - golden} dev); raw files in {args.raw_dir}")


if __name__ == "__main__":
    main()
