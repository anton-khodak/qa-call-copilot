"""Frontier reference backend: Claude via the local Claude Code CLI (`claude -p`) with `--json-schema`.

The prompt replaces the CLI's system prompt; tools, settings files and MCP servers are off and the CLI runs
in an empty directory, so no CLAUDE.md or project context reaches the model. The CLI has no sampling flags,
so only a sampling config without temperature/top_p/seed is accepted. Cost is the CLI's reported
`total_cost_usd` (list price, including prompt caching and thinking tokens).
"""

import json
import subprocess
import tempfile
import time
from pathlib import Path

from src.clients.base import Completion, FatalClientError, RequestError
from src.clients.retry import call_with_retry
from src.config import ROOT, ModelConfig, SamplingConfig


class _Retryable(Exception):
    """CLI timeout, rate limit or overload; retried."""


RETRY_STATUS = {429, 500, 502, 503, 529}


class ClaudeCodeClient:
    def __init__(self, config: ModelConfig, runner=subprocess.run):
        self.config = config
        self.runner = runner
        self.sleep = time.sleep
        self.repo_root = ROOT
        self.cwd = tempfile.mkdtemp(prefix="claude_extract_")

    def _command(self, system: str, schema: dict) -> list[str]:
        return [
            "claude", "-p",
            "--model", self.config.model_id,
            "--output-format", "json",
            "--system-prompt", system,
            "--json-schema", json.dumps(schema),
            "--tools", "",
            "--setting-sources", "",
            "--strict-mcp-config",
            "--no-session-persistence",
        ]

    def complete(self, system: str, user: str, schema: dict, sampling: SamplingConfig) -> Completion:
        if sampling.temperature is not None or sampling.top_p is not None or sampling.seed is not None:
            raise FatalClientError(
                f"the claude CLI cannot set temperature/top_p/seed; use sampling cli_default, not {sampling.name!r}")
        cmd = self._command(system, schema)

        def call():
            try:
                proc = self.runner(cmd, input=user, capture_output=True, text=True, cwd=self.cwd,
                                   timeout=self.config.timeout_s)
            except subprocess.TimeoutExpired as e:
                raise _Retryable(f"timeout after {self.config.timeout_s}s") from e
            try:
                out = json.loads(proc.stdout)
            except json.JSONDecodeError:
                raise RequestError(f"exit {proc.returncode}", (proc.stderr or proc.stdout)[:200])
            if out.get("is_error"):
                if out.get("api_error_status") in RETRY_STATUS:
                    raise _Retryable(f"API {out['api_error_status']}")
                message = str(out.get("result", ""))
                if "login" in message.lower():
                    raise FatalClientError(f"claude CLI is not logged in; run `claude` and /login ({message[:100]})")
                raise RequestError(f"API {out.get('api_error_status')}", message[:200])
            return out

        out = call_with_retry(call, self.config.max_attempts, (_Retryable,), sleep=self.sleep)
        usage = out.get("usage", {})
        input_tokens = sum(usage.get(k) or 0 for k in
                           ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
        structured = out.get("structured_output")
        text = json.dumps(structured) if structured is not None else out.get("result")
        return Completion(text, input_tokens, usage.get("output_tokens") or 0, cost_usd=out.get("total_cost_usd"))
