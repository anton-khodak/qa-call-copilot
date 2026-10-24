"""Local backend: Ollama native /api/chat with JSON-schema `format` and thinking off (spec §5)."""

import json
import time

import httpx2

from src.clients.base import Completion, FatalClientError, RequestError
from src.clients.retry import call_with_retry
from src.config import ModelConfig, SamplingConfig


class _ServerError(Exception):
    """HTTP 5xx from Ollama (e.g. busy loading a model); retried."""


RETRYABLE = (httpx2.TransportError, _ServerError)  # TransportError includes timeouts and refused connections


SCHEMA_HEADER = "## Output JSON schema (field meanings are in the descriptions)"


class OllamaClient:
    def __init__(self, config: ModelConfig, host: str, http: httpx2.Client | None = None):
        self.config = config
        self.host = host.rstrip("/")
        self.http = http or httpx2.Client()
        self.sleep = time.sleep

    def _missing(self) -> FatalClientError:
        return FatalClientError(f"model {self.config.model_id} not available; run `ollama pull {self.config.model_id}`")

    def check_ready(self) -> None:
        """Fail fast before a run if the server is down or the model is not pulled."""
        try:
            tags = self.http.get(f"{self.host}/api/tags", timeout=10).json()
        except httpx2.TransportError as e:
            raise FatalClientError(f"Ollama not reachable at {self.host}; start it with `ollama serve`") from e
        names = {m["name"] for m in tags.get("models", [])}
        if self.config.model_id not in names:
            raise self._missing()

    def complete(self, system: str, user: str, schema: dict, sampling: SamplingConfig) -> Completion:
        options = {"temperature": sampling.temperature, "top_p": sampling.top_p}
        if sampling.seed is not None:
            options["seed"] = sampling.seed
        if self.config.context_tokens:
            options["num_ctx"] = self.config.context_tokens
        if self.config.max_output_tokens:
            options["num_predict"] = self.config.max_output_tokens
        # `format` only constrains decoding; OpenAI also shows the schema to the model, Ollama does not
        system = f"{system}\n\n{SCHEMA_HEADER}\n{json.dumps(schema, indent=1)}"
        body = {
            "model": self.config.model_id,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "format": schema,
            "think": False,
            "stream": False,
            "options": options,
        }

        def call():
            resp = self.http.post(f"{self.host}/api/chat", json=body, timeout=self.config.timeout_s)
            if resp.status_code >= 500:
                raise _ServerError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            return resp

        resp = call_with_retry(call, self.config.max_attempts, RETRYABLE, sleep=self.sleep)
        if resp.status_code == 404:
            raise self._missing()
        if resp.status_code >= 400:
            raise RequestError(f"HTTP {resp.status_code}", resp.text[:200])
        data = resp.json()
        input_tokens = data.get("prompt_eval_count") or 0
        warnings = []
        if self.config.context_tokens and input_tokens >= self.config.context_tokens:
            warnings.append(f"context_full:{input_tokens}")
        output_tokens = data.get("eval_count") or 0
        if data.get("done_reason") == "length":
            warnings.append(f"output_truncated:{output_tokens}")
        return Completion(data["message"].get("content"), input_tokens, output_tokens, warnings)
