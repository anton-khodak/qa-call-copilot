"""OpenRouter backend via the OpenAI SDK, JSON-schema structured output."""

import time

import openai

from src.clients.base import Completion
from src.clients.retry import call_with_retry
from src.config import ModelConfig, SamplingConfig



class EmptyResponseError(Exception):
    """HTTP 200 without choices: OpenRouter reports upstream failures this way, with an "error" field."""


RETRYABLE = (
    openai.APITimeoutError,
    openai.APIConnectionError,
    openai.RateLimitError,
    openai.InternalServerError,
    EmptyResponseError,
)


class ProviderClient:
    def __init__(self, config: ModelConfig, api_key: str, sdk: openai.OpenAI | None = None):
        self.config = config
        # SDK retries off: call_with_retry owns them so attempts are visible and testable.
        self.sdk = sdk or openai.OpenAI(base_url=config.base_url, api_key=api_key, max_retries=0)
        self.sleep = time.sleep

    def complete(self, system: str, user: str, schema: dict, sampling: SamplingConfig) -> Completion:
        def call():
            resp = self.sdk.chat.completions.create(
                model=self.config.model_id,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "call_qa_record", "strict": True, "schema": schema},
                },
                temperature=sampling.temperature,
                top_p=sampling.top_p,
                seed=sampling.seed,
                timeout=self.config.timeout_s,
            )
            if not resp.choices:
                raise EmptyResponseError(str(getattr(resp, "error", None) or "no choices in response"))
            return resp

        resp = call_with_retry(call, self.config.max_attempts, RETRYABLE, sleep=self.sleep)
        usage = resp.usage
        return Completion(
            text=resp.choices[0].message.content,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )
