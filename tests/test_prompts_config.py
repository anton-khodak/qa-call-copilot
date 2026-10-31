import pytest

from src.config import load_model, load_sampling
from src.prompts import build_repair_message, build_user_message, load_prompt


def test_prompt_hash_stable_and_short():
    p = load_prompt("v1")
    assert p.version == "v1" and len(p.hash) == 12 and p.hash == load_prompt("v1").hash


def test_prompt_hash_changes_with_text(tmp_path):
    (tmp_path / "extract_va.md").write_text("abc")
    (tmp_path / "extract_vb.md").write_text("abd")
    assert load_prompt("va", tmp_path).hash != load_prompt("vb", tmp_path).hash


def test_prompt_v1_covers_required_topics():
    t = load_prompt("v1").text.lower()
    for kw in ["null", "unknown", "not_applicable", "speaker", "asr", "benefits", "verbatim"]:
        assert kw in t, kw


def test_user_message_wraps_raw():
    assert build_user_message(" a ") == "<transcript>\n a \n</transcript>"


def test_repair_message_wraps_transcript_and_error():
    m = build_repair_message(" a ", '{"x": 1}', "validation_error:outcome: bad")
    assert m.startswith("<transcript>\n a \n</transcript>")
    assert '<previous_output>\n{"x": 1}\n</previous_output>' in m and "validation_error:outcome: bad" in m


def test_load_model():
    m = load_model("gpt4o_mini")
    assert m.provider == "openrouter" and m.timeout_s == 60 and m.max_attempts == 3


def test_load_sampling():
    s = load_sampling("deterministic")
    assert (s.temperature, s.top_p, s.seed) == (0.0, 1.0, 42)


def test_unknown_name_raises_keyerror_listing_options():
    with pytest.raises(KeyError, match="gpt4o_mini"):
        load_model("nope")
    with pytest.raises(KeyError, match="deterministic"):
        load_sampling("nope")
