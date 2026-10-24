# Call QA & Compliance Copilot — stage 1: structured extraction

Turns raw call-centre transcripts ([CallCenterEN](https://huggingface.co/datasets/AIxBlock/92k-real-world-call-center-scripts-english)) into validated JSON QA records (`src/schema.py`) using an LLM with structured output.

## Install

Requires Python 3.11+, managed with [uv](https://docs.astral.sh/uv/), and [Ollama](https://ollama.com) for the local model.

```bash
brew install uv ollama  # or see the uv / Ollama docs for other platforms
uv sync
cp .env.example .env    # then fill in OPENROUTER_API_KEY; OLLAMA_HOST defaults to http://localhost:11434
ollama serve &          # if Ollama is not already running
ollama pull qwen3:8b    # ~5 GB; runs with thinking off and a 16k context
```

`HF_TOKEN` is optional (the dataset is not gated).

## Run

```bash
make data   # fetch the calls listed in data/manifest.csv into data/raw/ (gitignored)
make run    # every model x prompt x sampling combination (golden calls 3 runs each), then metrics
make eval   # recompute metrics from results/runs/ (e.g. after filling in golden labels)
make test   # unit tests (no network)
```

`make run` is `python main.py matrix`: it checks the API key, Ollama and the data first, prints the total cost estimate and asks before spending. Options: `--models`, `--prompts`, `--samplings`, `--golden-runs N`, `--split all|golden|dev`, `--yes`. `python main.py run` runs a single combination (`--model`, `--prompt`, `--sampling`).

Metrics (spec §11) go to `results/metrics.csv`, `results/per_class.csv` and `results/metrics.md`. Only the latest run of each combination is scored; golden accuracy is the median across runs, and a failed record counts as wrong.

Results go to `results/runs/<run_id>.jsonl`, one line per call and run, with model, prompt version and hash, sampling, status, latency, tokens, cost, code-check warnings, raw output and the parsed record.

## Layout

- `src/schema.py`: Pydantic QA record (`schema_version = "v1"`)
- `src/dataset.py`, `data/download.py`: call selection, manifest, transcript loading
- `src/clients/`: model interface, OpenRouter backend, Ollama backend, retry/backoff
- `src/eval.py`: metrics against the golden set and source domains
- `src/extract.py`: model call, schema validation, code checks (`src/checks.py`)
- `prompts/`: versioned prompts and `CHANGELOG.md`
- `config/`: models (prices, timeouts, retries) and sampling configs

Raw transcripts are CC BY-NC 4.0 and are not committed; `data/manifest.csv` records exactly which calls are used.
