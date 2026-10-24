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
    assert run_checks(rec, T, "plan_sales") == []


def test_disclaimer_on_non_plan_sales_flagged():
    rec = _rec(call_type="medical_equipment", compliance={
        "recording_disclosed": {"value": True, "evidence": "this call may be recorded"},
        "disclaimer_before_benefits": {"value": "yes", "evidence": None},
    })
    assert "disclaimer_not_plan_sales" in run_checks(rec, T, "medical_equipment")


def test_call_type_mismatch_flagged():
    rec = _rec(call_type="member_service")
    assert run_checks(rec, T, "plan_sales") == ["call_type_mismatch:predicted=member_service,source=plan_sales"]


def test_clean_record_no_warnings():
    assert run_checks(_rec(), T, "plan_sales") == []


def test_invented_evidence_in_record_flagged():
    rec = _rec(compliance={
        "recording_disclosed": {"value": True, "evidence": "calls are monitored by our legal team"},
        "disclaimer_before_benefits": {"value": "no", "evidence": "we do not offer every plan"},
    })
    assert run_checks(rec, T, "plan_sales") == [
        "evidence_not_found:recording_disclosed",
        "evidence_not_found:disclaimer_before_benefits",
    ]


def test_checks_do_not_mutate_record():
    rec = _rec(call_type="member_service")
    before = rec.model_dump()
    run_checks(rec, T, "plan_sales")
    assert rec.model_dump() == before
