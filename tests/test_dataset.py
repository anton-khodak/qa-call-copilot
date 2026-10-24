import io
import json
import zipfile

from src import dataset
from src.dataset import (
    ManifestRow,
    assign_splits,
    call_id_from_member,
    load_transcript,
    read_manifest,
    select_members,
    write_manifest,
)


def _row(call_id, domain="medicare", split="", **kw):
    base = dict(
        call_id=call_id, domain=domain, zip_name="z.zip", member=f"d/{call_id}_transcript.json",
        file_size=100, audio_duration=None, word_count=None, split=split,
    )
    return ManifestRow(**{**base, **kw})


def test_call_id_from_member():
    m = "auto_insurance_customer_service_inbound/2020-07-17-14-44-38_318178f6-bb02_v2fH_transcript.json"
    assert call_id_from_member(m) == "2020-07-17-14-44-38_318178f6-bb02_v2fH"
    assert call_id_from_member("__MACOSX/auto/._x_transcript.json") is None
    assert call_id_from_member("auto/") is None


def test_select_members_deterministic_and_spans_quartiles():
    members = [(f"d/c{i}_transcript.json", i * 100) for i in range(200)]
    a, b = select_members(members, 12, 42), select_members(members, 12, 42)
    assert a == b and len(a) == 12
    sizes = sorted(s for _, s in a)
    assert sizes[0] < 5000 and sizes[-1] > 15000
    assert sum(s < 1000 for s in sizes) == 3  # bottom 5%: short/broken calls (spec §3)


def test_select_members_skips_empty_files():
    members = [("d/empty_transcript.json", 0)] + [(f"d/c{i}_transcript.json", 100 + i) for i in range(100)]
    assert all(s > 0 for _, s in select_members(members, 12, 42))


def test_assign_splits_counts():
    rows = [_row(f"{d}{i}", d) for d in ("medicare", "auto_insurance", "home_services") for i in range(12)]
    out = assign_splits(rows)
    golden = [r for r in out if r.split == "golden"]
    assert {d: sum(r.domain == d for r in golden) for d in ("medicare", "auto_insurance", "home_services")} == {
        "medicare": 4, "auto_insurance": 3, "home_services": 3,
    }
    assert sum(r.split == "dev" for r in out) == 26
    assert [r.split for r in out] == [r.split for r in assign_splits(rows)]


def test_manifest_roundtrip(tmp_path):
    rows = [_row("a", split="golden", audio_duration=12.5, word_count=40), _row("b", split="dev")]
    p = tmp_path / "m.csv"
    write_manifest(p, rows)
    assert read_manifest(p) == rows


def _write_raw(raw, domain, call_id, text):
    (raw / domain).mkdir(parents=True, exist_ok=True)
    payload = {"text": text, "confidence": 0.9, "audio_duration": 12, "words": [{"text": "Hi"}], "redacted_pii_policies": []}
    (raw / domain / f"{call_id}.json").write_text(json.dumps(payload))


def test_load_transcript_keeps_text_raw(tmp_path):
    _write_raw(tmp_path, "medicare", "a", "  Hi [PERSON_NAME]..  ")
    t = load_transcript(_row("a", split="dev"), tmp_path)
    assert t.text == "  Hi [PERSON_NAME]..  "
    assert (t.call_id, t.domain, t.split, t.audio_duration) == ("a", "medicare", "dev", 12)
    assert t.words == [{"text": "Hi"}]


def test_load_transcript_empty_text_ok(tmp_path):
    _write_raw(tmp_path, "medicare", "a", "")
    assert load_transcript(_row("a"), tmp_path).text == ""


def _fake_zip(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for m in members:
            z.writestr(m, json.dumps({"text": "hello there", "audio_duration": 5, "words": [{}, {}]}))
    buf.seek(0)
    return zipfile.ZipFile(buf)


def test_download_uses_existing_manifest(tmp_path, monkeypatch):
    import data.download as dl

    rows = [_row("a", split="golden"), _row("b", split="dev")]
    manifest = tmp_path / "manifest.csv"
    write_manifest(manifest, rows)
    read = []
    zf = _fake_zip([r.member for r in rows] + ["d/c_transcript.json"])
    real_read = zf.read
    zf.read = lambda name: (read.append(name), real_read(name))[1]
    monkeypatch.setattr(dl, "open_zip", lambda name: zf)
    monkeypatch.setattr(dl, "select_members", lambda *a, **k: (_ for _ in ()).throw(AssertionError("reselected")))

    dl.main(["--manifest", str(manifest), "--raw-dir", str(tmp_path / "raw")])

    assert sorted(read) == sorted(r.member for r in rows)
    assert (tmp_path / "raw" / "medicare" / "a.json").exists()
    assert read_manifest(manifest) == rows


def test_medicare_source_is_insurance_outbound():
    # medicare_inbound.zip is ~95% non-Medicare (vet clinics etc.); insurance_outbound.zip is ~96% Medicare
    assert dataset.DOMAIN_ZIPS["medicare"] == "insurance_outbound.zip"
