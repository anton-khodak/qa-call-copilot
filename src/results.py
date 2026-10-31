"""Result records, one JSONL line per (call x model x prompt x sampling x run) (spec §9)."""

import json
from datetime import datetime, timezone
from pathlib import Path

from src.config import ModelConfig, SamplingConfig
from src.dataset import Transcript
from src.extract import ExtractionResult
from src.prompts import Prompt
from src.schema import SCHEMA_VERSION


def cost_usd(input_tokens: int, output_tokens: int, model: ModelConfig) -> float:
    return (input_tokens * model.price_input_per_1m + output_tokens * model.price_output_per_1m) / 1e6


def build_record(
    run_id: str,
    transcript: Transcript,
    model: ModelConfig,
    prompt: Prompt,
    sampling: SamplingConfig,
    run_idx: int,
    result: ExtractionResult,
) -> dict:
    return {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "call_id": transcript.call_id,
        "split": transcript.split,
        "model": model.model_id,
        "provider": model.provider,
        "prompt_version": prompt.version,
        "prompt_hash": prompt.hash,
        "schema_version": SCHEMA_VERSION,
        "sampling_name": sampling.name,
        "temperature": sampling.temperature,
        "top_p": sampling.top_p,
        "seed": sampling.seed,
        "run_idx": run_idx,
        "status": result.status,
        "latency_ms": result.latency_ms,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "cost_usd": cost_usd(result.input_tokens, result.output_tokens, model),
        "warnings": result.warnings,
        "first_raw_output": result.first_raw_output,
        "raw_output": result.raw_output,
        "parsed": result.parsed,
    }


def append_jsonl(path: Path, record: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
