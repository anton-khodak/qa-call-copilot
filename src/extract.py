"""One extraction: call the model, validate against the schema, run code checks (spec §4, §8)."""

import time
from dataclasses import dataclass, field
from typing import Literal

import openai
import pydantic

from src.checks import run_checks
from src.clients.base import ModelClient, TransportError
from src.config import SamplingConfig
from src.dataset import Transcript
from src.prompts import Prompt, build_user_message
from src.schema import CallQARecord, strict_json_schema

FATAL_STATUS = (401, 402, 403)  # bad key, no credits, forbidden: every later call would fail too

Status = Literal["valid_first_try", "valid_after_repair", "failed"]


@dataclass
class ExtractionResult:
    status: Status
    parsed: dict | None
    raw_output: str | None
    warnings: list[str] = field(default_factory=list)
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


def validate_output(raw: str | None) -> tuple[CallQARecord | None, str | None]:
    """Return (record, None) if raw is a valid CallQARecord, else (None, warning)."""
    if not raw:
        return None, "empty_output"
    try:
        return CallQARecord.model_validate_json(raw), None
    except pydantic.ValidationError as e:
        err = e.errors()[0]
        loc = ".".join(str(p) for p in err["loc"]) or "<root>"
        return None, f"validation_error:{loc}: {err['msg']}"


def extract(client: ModelClient, transcript: Transcript, prompt: Prompt, sampling: SamplingConfig) -> ExtractionResult:
    start = time.perf_counter()
    try:
        completion = client.complete(prompt.text, build_user_message(transcript.text), strict_json_schema(), sampling)
    except TransportError as e:
        return ExtractionResult("failed", None, None, [f"transport_error:{type(e.last).__name__}"], _ms(start))
    except openai.APIStatusError as e:
        if e.status_code in FATAL_STATUS:
            raise
        return ExtractionResult("failed", None, None, [f"request_error:{type(e).__name__}"], _ms(start))
    except Exception as e:  # one bad response must not stop a paid multi-call run
        return ExtractionResult("failed", None, None, [f"unexpected_error:{type(e).__name__}: {e}"], _ms(start))
    latency = _ms(start)
    tokens = dict(input_tokens=completion.input_tokens, output_tokens=completion.output_tokens)

    record, error = validate_output(completion.text)
    if record is None:
        return ExtractionResult("failed", None, completion.text, [error], latency, **tokens)
    warnings = run_checks(record, transcript.text, transcript.domain)
    return ExtractionResult("valid_first_try", record.model_dump(mode="json"), completion.text, warnings, latency, **tokens)


def _ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)
