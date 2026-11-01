# Call QA & Compliance Copilot — stage 1: structured extraction

Turns raw Medicare sales and service call transcripts ([CallCenterEN](https://huggingface.co/datasets/AIxBlock/92k-real-world-call-center-scripts-english)) into validated JSON QA records (`src/schema.py`) using an LLM with structured output, and measures how well different models, prompts and sampling settings do it.

## For reviewers

Start with **`REPORT.md`** (summary, comparison tables, error analysis, production choice). `make eval` recomputes every number in it from the committed runs in seconds, with no API key or Ollama.

| Grading criterion | Where |
|---|---|
| Schema: ≥ 6 fields, enum, nested structure | `src/schema.py`: 6 fields, 4 enums, nested `objections` list and `compliance` object; field descriptions are the definitions sent to the model |
| Structured output + retry and timeout | `src/clients/provider.py` (OpenAI strict JSON schema via OpenRouter), `src/clients/local.py` (Ollama `format`), `src/clients/retry.py` (exponential backoff); timeouts and attempts in `config/models.yaml` |
| All texts run, results saved | `results/runs/*.jsonl`: 36 calls per combination, golden calls ×3 |
| Local model behind the same interface | `src/clients/base.py` (`ModelClient`), implemented by the OpenRouter, Ollama and Claude Code backends |
| Sampling in config, ≥ 2 configs compared | `config/sampling.yaml`: `deterministic`, `low` (and `cli_default` for Opus) |
| Accuracy, validity, latency, cost | `src/eval.py` → `results/metrics.md`, `metrics.csv`, `per_class.csv` |
| ≥ 2 prompt versions with changelog | `prompts/extract_v1.md` (minimal baseline), `prompts/extract_v2.md` (one section per dev-set error class), `prompts/CHANGELOG.md` (what changed, why, with dev-set counts) |
| Validation + handling invalid output | `src/extract.py`: Pydantic validation, one repair call with the validation error, then `failed`; tests in `tests/test_extract.py` |
| Logging model, prompt version, sampling | `src/results.py`: every record carries model, provider, prompt version and hash, schema version, sampling name, temperature, top_p, seed, status, latency, tokens, cost |
| Comparison table, 3–5 errors, final choice | `REPORT.md`; every golden disagreement in `results/golden_errors.csv` (`make errors`) |
| README, one command, keys not in code | this file; `make run`; keys only in `.env` (template `.env.example`) |

- **Data:** 36 Medicare calls, 10 of them the golden set (`data/README.md`). Golden labels in `data/golden/golden.jsonl`, made by hand per `data/golden/LABELING.md` and adjudicated against blind labels from two models (`opus.jsonl`, `astra.jsonl`; every decision in `review.json`).
- **Design spec:** `spec.md` (written before implementation; code docstrings cite its sections).
- **Stretch:** a third model (`qwen3:14b`, to isolate model size) and a frontier reference (Claude Opus 5.5 through the local Claude Code CLI, `make frontier`).
- **Tests:** `make test`, 137 unit tests, no network.

## Install

Requires Python 3.11+, managed with [uv](https://docs.astral.sh/uv/), and [Ollama](https://ollama.com) for the local model.

```bash
brew install uv ollama  # or see the uv / Ollama docs for other platforms
uv sync
cp .env.example .env    # then fill in OPENROUTER_API_KEY; OLLAMA_HOST defaults to http://localhost:11434
ollama serve &          # if Ollama is not already running
ollama pull qwen3:8b    # ~5 GB; runs with thinking off and a 16k context
ollama pull qwen3:14b   # ~9 GB; same family, size comparison
```

`HF_TOKEN` is optional (the dataset is not gated).

## Run

```bash
make run    # runs every model x prompt (v1, v2) x sampling on the 36 transcripts in data/raw/, then metrics
make frontier # Opus 5.5 reference through the local Claude Code CLI, both prompts, then metrics
make eval   # recompute metrics from results/runs/ without calling any model
make errors # export golden-set disagreements to results/golden_errors.csv
make test   # unit tests (no network)
make label  # local UI for labelling / adjudicating the golden set
```

A full `make run` (both prompt versions) costs about $0.10 on OpenRouter and takes about an hour and a half on an Apple M-series laptop, almost all of it the local models (qwen3:14b ~13 s per call, qwen3:8b ~6 s, gpt-4o-mini ~1.3 s). For a quicker check, skip the 14B model:

```bash
make run ARGS="--models gpt4o_mini qwen3_8b"                     # ~30 min
make run ARGS="--models gpt4o_mini --split golden --prompts v2"  # ~2 min, API only, no Ollama needed
```

`make frontier` needs [Claude Code](https://claude.com/claude-code) installed and logged in; it runs Opus 5.5 on both prompts in about 12 minutes (6 if the two prompts run in parallel with `python main.py run`) for about $2.70 at list price, billed to that login.

The 36 transcripts are committed in `data/raw/` (licence and attribution in `data/README.md`); `make data` re-downloads any that are missing.

`make run` is `python main.py matrix`: it checks the API key, Ollama and the data first, prints the total cost estimate and asks before spending (`ARGS=--yes` skips the question). Options: `--models`, `--prompts`, `--samplings`, `--golden-runs N`, `--split all|golden|dev`, `--yes`. `python main.py run` runs a single combination (`--model`, `--prompt`, `--sampling`).

Metrics (spec §11) go to `results/metrics.csv`, `results/per_class.csv` and `results/metrics.md`. Only the latest run of each combination is scored; golden accuracy is the median across runs, and a failed record counts as wrong.

Results go to `results/runs/<run_id>.jsonl`, one line per call and run, with model, prompt version and hash, sampling (name, temperature, top_p, seed), status (`valid_first_try` / `valid_after_repair` / `failed`), latency, tokens and cost (both calls when repaired; for Opus the cost the CLI reports), code-check warnings, the raw output before repair (if any), the final raw output and the parsed record.

## Layout

- `src/schema.py`: Pydantic QA record (`SCHEMA_VERSION = "v1"`)
- `src/dataset.py`, `data/download.py`: call selection, manifest, transcript loading
- `src/clients/`: model interface, OpenRouter backend, Ollama backend, Claude Code CLI backend (frontier reference), retry/backoff
- `src/eval.py`: metrics against the golden set and source call types
- `src/label_app.py`: local labelling and adjudication UI for the golden set (`make label`)
- `src/extract.py`: model call, schema validation, one repair attempt, code checks (`src/checks.py`)
- `src/errors.py`: golden-set disagreements for the error analysis (`make errors`)
- `prompts/`: versioned prompts and `CHANGELOG.md`
- `config/`: models (prices, timeouts, retries) and sampling configs

Transcripts are CC BY-NC 4.0 (AIxBlock); `data/manifest.csv` records exactly which calls are used.
