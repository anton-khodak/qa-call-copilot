"""Backend-agnostic model interface (spec §5). Provider and local backends implement ModelClient."""

from dataclasses import dataclass, field
from typing import Protocol

from src.config import ModelConfig, SamplingConfig


@dataclass
class Completion:
    text: str | None
    input_tokens: int
    output_tokens: int
    warnings: list[str] = field(default_factory=list)
    cost_usd: float | None = None  # set when the backend reports actual cost (caching, thinking)


class TransportError(Exception):
    """Raised when a call still fails after all retry attempts."""

    def __init__(self, last: BaseException, attempts: int):
        super().__init__(f"{type(last).__name__} after {attempts} attempts: {last}")
        self.last = last
        self.attempts = attempts


class RequestError(Exception):
    """Non-retryable error for this one request (e.g. HTTP 400); the run continues."""

    def __init__(self, kind: str, message: str = ""):
        super().__init__(f"{kind}: {message}" if message else kind)
        self.kind = kind


class FatalClientError(Exception):
    """Error every later call would hit too (bad key, no credits, model missing); the run aborts."""


class ModelClient(Protocol):
    config: ModelConfig

    def complete(self, system: str, user: str, schema: dict, sampling: SamplingConfig) -> Completion: ...
