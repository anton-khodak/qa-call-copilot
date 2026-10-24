"""Code checks run after schema validation (spec §4). They only add warnings; the
model's output is never changed."""

import re

from rapidfuzz import fuzz

from src.schema import CallQARecord, CallType, DisclaimerValue

_PUNCT = re.compile(r"[^\w\s\[\]]")
_SPACE = re.compile(r"\s+")


def _normalise(s: str) -> str:
    return _SPACE.sub(" ", _PUNCT.sub(" ", s.lower())).strip()


def evidence_matches(quote: str, transcript: str, threshold: int = 90) -> bool:
    q = _normalise(quote)
    if not q:
        return False
    return fuzz.partial_ratio(q, _normalise(transcript)) >= threshold


def run_checks(record: CallQARecord, transcript: str, source_call_type: str) -> list[str]:
    warnings = []
    for name in ("recording_disclosed", "disclaimer_before_benefits"):
        evidence = getattr(record.compliance, name).evidence
        if evidence is not None and not evidence_matches(evidence, transcript):
            warnings.append(f"evidence_not_found:{name}")
    if (
        record.compliance.disclaimer_before_benefits.value != DisclaimerValue.not_applicable
        and record.call_type != CallType.plan_sales
    ):
        warnings.append("disclaimer_not_plan_sales")
    if record.call_type.value != source_call_type:
        warnings.append(f"call_type_mismatch:predicted={record.call_type.value},source={source_call_type}")
    return warnings
