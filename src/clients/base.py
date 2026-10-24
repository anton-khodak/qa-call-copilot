"""Backend-agnostic model interface (spec §5). Provider and local backends implement ModelClient."""

from dataclasses import dataclass
from typing import Protocol

from src.config import ModelConfig, SamplingConfig


@dataclass
class Completion:
    text: str | None
    input_tokens: int
    output_tokens: int


class TransportError(Exception):
    """Raised when a call still fails after all retry attempts."""

    def __init__(self, last: BaseException, attempts: int):
        super().__init__(f"{type(last).__name__} after {attempts} attempts: {last}")
        self.last = last
        self.attempts = attempts


class ModelClient(Protocol):
    config: ModelConfig

    def complete(self, system: str, user: str, schema: dict, sampling: SamplingConfig) -> Completion: ...
