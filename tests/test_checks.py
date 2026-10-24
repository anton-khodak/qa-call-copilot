from src.checks import evidence_matches, run_checks
from src.schema import CallQARecord
from tests.test_schema import VALID

T = "Hi, this call may be recorded for quality and training purposes. How can I help?"


def _rec(**over):
    d = {**VALID, "compliance": {
        "recording_disclosed": {"value": True, "evidence": "this call may be recorded"},
        "disclaimer_before_benefits": {"value": "not_applicable", "evidence": None},
    }}
    d.update(over)
    return CallQARecord.model_validate(d)


def test_exact_quote_matches():
    assert evidence_matches("this call may be recorded", T)


def test_case_space_punct_tolerant():
    assert evidence_matches("This call  may be RECORDED,", T)


def test_invented_quote_flagged():
    assert not evidence_matches("you agree to our terms of service", T)


def test_null_evidence_no_flag():
    rec = _rec(compliance={
        "recording_disclosed": {"value": None, "evidence": None},
        "disclaimer_before_benefits": {"value": "not_applicable", "evidence": None},
    })
    assert run_checks(rec, T, "medicare") == []


def test_disclaimer_on_non_medicare_flagged():
    rec = _rec(domain="auto_insurance", compliance={
        "recording_disclosed": {"value": True, "evidence": "this call may be recorded"},
        "disclaimer_before_benefits": {"value": "yes", "evidence": None},
    })
    assert "disclaimer_not_medicare" in run_checks(rec, T, "auto_insurance")


def test_domain_mismatch_flagged():
    rec = _rec(domain="home_services")
    assert run_checks(rec, T, "medicare") == ["domain_mismatch:predicted=home_services,source=medicare"]


def test_clean_record_no_warnings():
    assert run_checks(_rec(), T, "medicare") == []


def test_invented_evidence_in_record_flagged():
    rec = _rec(compliance={
        "recording_disclosed": {"value": True, "evidence": "calls are monitored by our legal team"},
        "disclaimer_before_benefits": {"value": "no", "evidence": "we do not offer every plan"},
    })
    assert run_checks(rec, T, "medicare") == [
        "evidence_not_found:recording_disclosed",
        "evidence_not_found:disclaimer_before_benefits",
    ]


def test_checks_do_not_mutate_record():
    rec = _rec(domain="home_services")
    before = rec.model_dump()
    run_checks(rec, T, "medicare")
    assert rec.model_dump() == before
