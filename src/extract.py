"""One extraction: call the model, validate against the schema, repair once if invalid, run code checks
(spec §4, §8)."""

import time
from dataclasses import dataclass, field
from typing import Literal

import pydantic

from src.checks import run_checks
from src.clients.base import Completion, FatalClientError, ModelClient, RequestError, TransportError
from src.config import SamplingConfig
from src.dataset import Transcript
from src.prompts import Prompt, build_repair_message, build_user_message
from src.schema import CallQARecord, strict_json_schema

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
    first_raw_output: str | None = None  # set only when a repair was attempted
    cost_usd: float | None = None  # backend-reported cost; None means price it from tokens


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


def _complete(client: ModelClient, system: str, user: str, sampling: SamplingConfig) -> tuple[Completion | None, str | None]:
    """One model call; returns (completion, None) or (None, warning). FatalClientError propagates."""
    try:
        return client.complete(system, user, strict_json_schema(), sampling), None
    except TransportError as e:
        return None, f"transport_error:{type(e.last).__name__}"
    except RequestError as e:
        return None, f"request_error:{e.kind}"
    except FatalClientError:
        raise
    except Exception as e:  # one bad response must not stop a paid multi-call run
        return None, f"unexpected_error:{type(e).__name__}: {e}"


def extract(client: ModelClient, transcript: Transcript, prompt: Prompt, sampling: SamplingConfig) -> ExtractionResult:
    start = time.perf_counter()
    completion, error = _complete(client, prompt.text, build_user_message(transcript.text), sampling)
    if completion is None:
        return ExtractionResult("failed", None, None, [error], _ms(start))
    warnings = list(completion.warnings)
    tokens = [completion.input_tokens, completion.output_tokens]
    cost = completion.cost_usd
    record, error = validate_output(completion.text)
    if record is not None:
        warnings += run_checks(record, transcript.text, transcript.source_call_type)
        return ExtractionResult("valid_first_try", record.model_dump(mode="json"), completion.text, warnings,
                                _ms(start), *tokens, cost_usd=cost)

    # Exactly one repair call with the validation error, then `failed` (spec §8).
    first_raw = completion.text
    warnings.append(error)
    repair_msg = build_repair_message(transcript.text, first_raw, error)
    repaired, call_error = _complete(client, prompt.text, repair_msg, sampling)
    if repaired is None:
        return ExtractionResult("failed", None, first_raw, warnings + [call_error], _ms(start), *tokens, first_raw,
                                cost)
    warnings += repaired.warnings
    tokens = [tokens[0] + repaired.input_tokens, tokens[1] + repaired.output_tokens]
    if repaired.cost_usd is not None:
        cost = (cost or 0.0) + repaired.cost_usd
    record, error = validate_output(repaired.text)
    if record is None:
        return ExtractionResult("failed", None, repaired.text, warnings + [error], _ms(start), *tokens, first_raw,
                                cost)
    warnings += run_checks(record, transcript.text, transcript.source_call_type)
    return ExtractionResult("valid_after_repair", record.model_dump(mode="json"), repaired.text, warnings,
                            _ms(start), *tokens, first_raw, cost)


def _ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)
