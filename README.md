# Call QA & Compliance Copilot — stage 1: structured extraction

Turns raw Medicare sales and service call transcripts ([CallCenterEN](https://huggingface.co/datasets/AIxBlock/92k-real-world-call-center-scripts-english)) into validated JSON QA records (`src/schema.py`) using an LLM with structured output, and measures how well different models, prompts and sampling settings do it.

## For reviewers

- **What and why:** `spec.md` (the assignment spec; the revision note at the top explains the Medicare-only scope).
- **Schema:** `src/schema.py`; field descriptions are the definitions sent to the model.
- **Report:** `REPORT.md`: comparison table, error analysis, production choice.
- **Prompts:** `prompts/extract_v1.md` (baseline) and `prompts/extract_v2.md` (fixes from dev-set errors); what changed and why in `prompts/CHANGELOG.md`.
- **Golden set:** 10 calls in `data/golden/golden_v2.jsonl`, labelled by hand per `data/golden/LABELING.md` and adjudicated against blind labels from two models (`opus_v2.jsonl`, `astra_v2.jsonl`; every decision in `review_v2.json`).
- **Results:** `results/metrics.md` (summary + per-field accuracy), `results/per_class.csv`, `results/golden_errors.csv` (every golden disagreement), raw runs in `results/runs/`. `results/archive/` holds superseded runs kept for the report: the first three-domain schema (metrics only) and qwen3 runs from before the Ollama client showed the schema to the model.
- **Validation and repair:** `src/extract.py`: schema validation, one repair call with the validation error, then `failed` (tests in `tests/test_extract.py`).
- **Status:** steps 1-4 done.


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
make eval   # recompute metrics from results/runs/ without calling any model
make errors # export golden-set disagreements to results/golden_errors.csv
make test   # unit tests (no network)
make label  # local UI for labelling / adjudicating the golden set
```

A full `make run` (both prompt versions) costs about $0.13 on OpenRouter and takes about two hours on an Apple M-series laptop, almost all of it the local models (qwen3:14b ~16 s per call, qwen3:8b ~8 s, gpt-4o-mini ~2 s). For a quicker check, skip the 14B model:

```bash
make run ARGS="--models gpt4o_mini qwen3_8b"                     # ~40 min
make run ARGS="--models gpt4o_mini --split golden --prompts v2"  # ~2 min, API only, no Ollama needed
```

The 36 transcripts are committed in `data/raw/` (licence and attribution in `data/README.md`); `make data` re-downloads any that are missing.

`make run` is `python main.py matrix`: it checks the API key, Ollama and the data first, prints the total cost estimate and asks before spending (`ARGS=--yes` skips the question). Options: `--models`, `--prompts`, `--samplings`, `--golden-runs N`, `--split all|golden|dev`, `--yes`. `python main.py run` runs a single combination (`--model`, `--prompt`, `--sampling`).

Metrics (spec §11) go to `results/metrics.csv`, `results/per_class.csv` and `results/metrics.md`. Only the latest run of each combination is scored; golden accuracy is the median across runs, and a failed record counts as wrong.

Results go to `results/runs/<run_id>.jsonl`, one line per call and run, with model, prompt version and hash, sampling (name, temperature, top_p, seed), status (`valid_first_try` / `valid_after_repair` / `failed`), latency, tokens and cost (both calls when repaired), code-check warnings, the raw output before repair (if any), the final raw output and the parsed record.

## Layout

- `src/schema.py`: Pydantic QA record (`SCHEMA_VERSION = "v2"`)
- `src/dataset.py`, `data/download.py`: call selection, manifest, transcript loading
- `src/clients/`: model interface, OpenRouter backend, Ollama backend, retry/backoff
- `src/eval.py`: metrics against the golden set and source call types
- `src/label_app.py`: local labelling and adjudication UI for the golden set (`make label`)
- `src/extract.py`: model call, schema validation, one repair attempt, code checks (`src/checks.py`)
- `src/errors.py`: golden-set disagreements for the error analysis (`make errors`)
- `prompts/`: versioned prompts and `CHANGELOG.md`
- `config/`: models (prices, timeouts, retries) and sampling configs

Transcripts are CC BY-NC 4.0 (AIxBlock); `data/manifest.csv` records exactly which calls are used.
