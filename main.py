"""One-command entry point: data check → extraction runs → results/runs/*.jsonl."""

import argparse
import collections
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from src.clients.base import ModelClient
from src.clients.provider import ProviderClient
from src.config import ModelConfig, load_model, load_sampling
from src.dataset import Transcript, load_calls, raw_path, read_manifest
from src.extract import extract
from src.prompts import Prompt, load_prompt
from src.results import append_jsonl, build_record, cost_usd

MANIFEST = Path("data/manifest.csv")
RAW_DIR = Path("data/raw")
API_KEYS = {"openrouter": "OPENROUTER_API_KEY"}


def make_client(model: ModelConfig) -> ModelClient:
    env = API_KEYS.get(model.provider)
    if env is None:
        raise SystemExit(f"unsupported provider {model.provider!r} for model {model.name!r}")
    key = os.getenv(env)
    if not key:
        raise SystemExit(f"{env} is not set; copy .env.example to .env and fill it in")
    return ProviderClient(model, key)


def check_raw_data() -> None:
    if not MANIFEST.exists():
        raise SystemExit(f"{MANIFEST} not found; run `make data` first")
    missing = [r.call_id for r in read_manifest(MANIFEST) if not raw_path(r, RAW_DIR).exists()]
    if missing:
        raise SystemExit(f"{len(missing)} transcripts missing from {RAW_DIR}; run `make data` first")


def estimate_cost(
    transcripts: list[Transcript], model: ModelConfig, runs: int, prompt: Prompt, output_tokens: int = 400
) -> float:
    input_tokens = sum((len(prompt.text) + len(t.text)) / 4 for t in transcripts)
    return runs * cost_usd(round(input_tokens), output_tokens * len(transcripts), model)


def run(args: argparse.Namespace) -> None:
    model = load_model(args.model)
    prompt = load_prompt(args.prompt)
    sampling = load_sampling(args.sampling)
    client = make_client(model)
    check_raw_data()
    calls = load_calls(args.split)

    est = estimate_cost(calls, model, args.runs, prompt)
    print(f"{len(calls)} calls x {args.runs} run(s) on {model.model_id}, prompt {prompt.version}, "
          f"sampling {sampling.name}: estimated cost ${est:.4f}")
    if not args.yes and input("Proceed? [y/N] ").strip().lower() != "y":
        raise SystemExit("aborted")

    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{model.name}_{prompt.version}_{sampling.name}"
    out = Path(args.out_dir) / f"{run_id}.jsonl"
    statuses, total = collections.Counter(), 0.0
    for t in calls:
        for run_idx in range(args.runs):
            result = extract(client, t, prompt, sampling)
            record = build_record(run_id, t, model, prompt, sampling, run_idx, result)
            append_jsonl(out, record)
            statuses[result.status] += 1
            total += record["cost_usd"]
            flags = f" {result.warnings}" if result.warnings else ""
            print(f"{t.call_id} [{run_idx}] {result.status} {result.latency_ms}ms{flags}")
    print(f"done: {dict(statuses)}, cost ${total:.4f}, results in {out}")


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="run extraction over the manifest calls")
    r.add_argument("--model", default="gpt4o_mini")
    r.add_argument("--prompt", default="v1")
    r.add_argument("--sampling", default="deterministic")
    r.add_argument("--split", default="all", choices=["all", "golden", "dev"])
    r.add_argument("--runs", type=int, default=1)
    r.add_argument("--out-dir", default="results/runs")
    r.add_argument("--yes", action="store_true", help="skip the cost confirmation prompt")
    args = p.parse_args(argv)
    if args.command == "run":
        run(args)


if __name__ == "__main__":
    sys.exit(main())
