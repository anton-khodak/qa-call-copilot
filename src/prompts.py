"""Versioned prompt files (prompts/extract_<version>.md, spec §6)."""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from src.config import ROOT


@dataclass(frozen=True)
class Prompt:
    version: str
    text: str
    hash: str


def load_prompt(version: str, prompts_dir: Path = ROOT / "prompts") -> Prompt:
    raw = (Path(prompts_dir) / f"extract_{version}.md").read_bytes()
    return Prompt(version=version, text=raw.decode("utf-8"), hash=hashlib.sha256(raw).hexdigest()[:12])


def build_user_message(transcript: str) -> str:
    return f"<transcript>\n{transcript}\n</transcript>"


def build_repair_message(transcript: str, previous_output: str | None, error: str) -> str:
    return (
        f"{build_user_message(transcript)}\n\n"
        "Your previous output was not valid against the schema.\n"
        f"<previous_output>\n{previous_output or ''}\n</previous_output>\n"
        f"Error: {error}\n"
        "Return the corrected JSON record only."
    )
