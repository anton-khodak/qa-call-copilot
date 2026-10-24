"""Model and sampling configs (config/models.yaml, config/sampling.yaml)."""

from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ModelConfig:
    name: str
    provider: str
    model_id: str
    base_url: str
    price_input_per_1m: float
    price_output_per_1m: float
    timeout_s: float
    max_attempts: int
    context_tokens: int | None = None  # local backends: context window to request (num_ctx)


@dataclass(frozen=True)
class SamplingConfig:
    name: str
    temperature: float
    top_p: float
    seed: int | None


def _entry(path: Path, section: str, name: str) -> dict:
    entries = yaml.safe_load(Path(path).read_text())[section]
    if name not in entries:
        raise KeyError(f"unknown {section} config {name!r}; available: {', '.join(entries)}")
    return entries[name]


def load_model(name: str, path: Path = ROOT / "config/models.yaml") -> ModelConfig:
    return ModelConfig(name=name, **_entry(path, "models", name))


def load_sampling(name: str, path: Path = ROOT / "config/sampling.yaml") -> SamplingConfig:
    e = _entry(path, "sampling", name)
    return SamplingConfig(name=name, temperature=e["temperature"], top_p=e["top_p"], seed=e.get("seed"))
