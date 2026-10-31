"""One-command entry point: data check → extraction runs → results/runs/*.jsonl → metrics."""

import argparse
import collections
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from src.clients.base import FatalClientError, ModelClient
from src.clients.local import OllamaClient
from src.clients.provider import ProviderClient
from src.config import ModelConfig, SamplingConfig, load_model, load_sampling
from src.dataset import Transcript, load_calls, raw_path, read_manifest
from src.errors import write_errors
from src.eval import evaluate
from src.extract import extract
from src.prompts import Prompt, load_prompt
from src.results import append_jsonl, build_record, cost_usd

MANIFEST = Path("data/manifest.csv")
RAW_DIR = Path("data/raw")
API_KEYS = {"openrouter": "OPENROUTER_API_KEY"}


def make_client(model: ModelConfig) -> ModelClient:
    if model.provider == "ollama":
        client = OllamaClient(model, os.getenv("OLLAMA_HOST") or model.base_url)
        try:
            client.check_ready()
        except FatalClientError as e:
            raise SystemExit(str(e))
        return client
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


def runs_for(t: Transcript, runs: int, golden_runs: int) -> int:
    return max(runs, golden_runs) if t.split == "golden" else runs


def estimate_cost(
    transcripts: list[Transcript], model: ModelConfig, runs: int, prompt: Prompt, output_tokens: int = 400,
    golden_runs: int = 1,
) -> float:
    total = 0.0
    for t in transcripts:
        n = runs_for(t, runs, golden_runs)
        total += n * cost_usd(round((len(prompt.text) + len(t.text)) / 4), output_tokens, model)
    return total


def run_combo(
    client: ModelClient, model: ModelConfig, prompt: Prompt, sampling: SamplingConfig,
    calls: list[Transcript], runs: int, golden_runs: int, out_dir: Path,
) -> Path:
    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_{model.name}_{prompt.version}_{sampling.name}"
    out = Path(out_dir) / f"{run_id}.jsonl"
    # Written as .partial and renamed when complete, so an aborted run never looks like a result set.
    partial = out.with_suffix(".jsonl.partial")
    statuses, total = collections.Counter(), 0.0
    print(f"== {model.name} / prompt {prompt.version} / {sampling.name}")
    for t in calls:
        for run_idx in range(runs_for(t, runs, golden_runs)):
            try:
                result = extract(client, t, prompt, sampling)
            except FatalClientError as e:
                raise SystemExit(f"aborting run: {e}. Partial results in {partial}")
            record = build_record(run_id, t, model, prompt, sampling, run_idx, result)
            append_jsonl(partial, record)
            statuses[result.status] += 1
            total += record["cost_usd"]
            flags = f" {result.warnings}" if result.warnings else ""
            print(f"{t.call_id} [{run_idx}] {result.status} {result.latency_ms}ms{flags}", flush=True)
    partial.rename(out)
    print(f"done: {dict(statuses)}, cost ${total:.4f}, results in {out}")
    return out


def _confirm(args: argparse.Namespace, estimate: float, what: str) -> None:
    print(f"{what}: estimated API cost ${estimate:.4f}")
    if not args.yes and input("Proceed? [y/N] ").strip().lower() != "y":
        raise SystemExit("aborted")


def run(args: argparse.Namespace) -> None:
    model, prompt, sampling = load_model(args.model), load_prompt(args.prompt), load_sampling(args.sampling)
    client = make_client(model)
    check_raw_data()
    calls = load_calls(args.split)
    est = estimate_cost(calls, model, args.runs, prompt, golden_runs=args.golden_runs)
    _confirm(args, est, f"{len(calls)} calls on {model.model_id}, prompt {prompt.version}, sampling {sampling.name}")
    run_combo(client, model, prompt, sampling, calls, args.runs, args.golden_runs, args.out_dir)


def matrix(args: argparse.Namespace) -> None:
    models = [load_model(m) for m in args.models]
    prompts = [load_prompt(p) for p in args.prompts]
    samplings = [load_sampling(s) for s in args.samplings]
    clients = {m.name: make_client(m) for m in models}  # fail fast on missing keys / Ollama before any call
    check_raw_data()
    calls = load_calls(args.split)
    combos = [(m, p, s) for m in models for p in prompts for s in samplings]
    est = sum(estimate_cost(calls, m, args.runs, p, golden_runs=args.golden_runs) for m, p, _ in combos)
    _confirm(args, est, f"{len(combos)} combinations x {len(calls)} calls")
    for m, p, s in combos:
        run_combo(clients[m.name], m, p, s, calls, args.runs, args.golden_runs, args.out_dir)
    evaluate(Path(args.out_dir), Path(args.out_dir).parent)


def _add_run_options(p: argparse.ArgumentParser, golden_runs: int) -> None:
    p.add_argument("--split", default="all", choices=["all", "golden", "dev"])
    p.add_argument("--runs", type=int, default=1, help="runs per call")
    p.add_argument("--golden-runs", type=int, default=golden_runs, help="runs per golden call (spec: 3-5)")
    p.add_argument("--out-dir", default="results/runs")
    p.add_argument("--yes", action="store_true", help="skip the cost confirmation prompt")


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="run one model / prompt / sampling combination")
    r.add_argument("--model", default="gpt4o_mini")
    r.add_argument("--prompt", default="v1")
    r.add_argument("--sampling", default="deterministic")
    _add_run_options(r, golden_runs=1)
    m = sub.add_parser("matrix", help="run every model x prompt x sampling combination, then evaluate")
    m.add_argument("--models", nargs="+", default=["gpt4o_mini", "qwen3_8b", "qwen3_14b"])
    m.add_argument("--prompts", nargs="+", default=["v1", "v2"])
    m.add_argument("--samplings", nargs="+", default=["deterministic", "low"])
    _add_run_options(m, golden_runs=3)
    e = sub.add_parser("eval", help="compute metrics from results/runs into results/")
    e.add_argument("--runs-dir", default="results/runs")
    e.add_argument("--out-dir", default="results")
    x = sub.add_parser("errors", help="export golden-set disagreements of the latest runs to a CSV")
    x.add_argument("--runs-dir", default="results/runs")
    x.add_argument("--out", default="results/golden_errors.csv")
    args = p.parse_args(argv)
    if args.command == "run":
        run(args)
    elif args.command == "matrix":
        matrix(args)
    elif args.command == "errors":
        write_errors(Path(args.runs_dir), Path(args.out))
    else:
        evaluate(Path(args.runs_dir), Path(args.out_dir))


if __name__ == "__main__":
    sys.exit(main())
