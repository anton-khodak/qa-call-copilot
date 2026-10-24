"""Code checks run after schema validation (spec §4). They only add warnings; the
model's output is never changed."""

import re

from rapidfuzz import fuzz

from src.schema import CallQARecord, DisclaimerValue, Domain

_PUNCT = re.compile(r"[^\w\s\[\]]")
_SPACE = re.compile(r"\s+")


def _normalise(s: str) -> str:
    return _SPACE.sub(" ", _PUNCT.sub(" ", s.lower())).strip()


def evidence_matches(quote: str, transcript: str, threshold: int = 90) -> bool:
    q = _normalise(quote)
    if not q:
        return False
    return fuzz.partial_ratio(q, _normalise(transcript)) >= threshold


def run_checks(record: CallQARecord, transcript: str, source_domain: str) -> list[str]:
    warnings = []
    for name in ("recording_disclosed", "disclaimer_before_benefits"):
        evidence = getattr(record.compliance, name).evidence
        if evidence is not None and not evidence_matches(evidence, transcript):
            warnings.append(f"evidence_not_found:{name}")
    if (
        record.compliance.disclaimer_before_benefits.value != DisclaimerValue.not_applicable
        and record.domain != Domain.medicare
    ):
        warnings.append("disclaimer_not_medicare")
    if record.domain.value != source_domain:
        warnings.append(f"domain_mismatch:predicted={record.domain.value},source={source_domain}")
    return warnings
