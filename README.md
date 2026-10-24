# Call QA & Compliance Copilot — stage 1: structured extraction

Turns raw call-centre transcripts ([CallCenterEN](https://huggingface.co/datasets/AIxBlock/92k-real-world-call-center-scripts-english)) into validated JSON QA records (`src/schema.py`) using an LLM with structured output.

## Install

Requires Python 3.11+, managed with [uv](https://docs.astral.sh/uv/).

```bash
brew install uv        # or see the uv docs for other platforms
uv sync
cp .env.example .env   # then fill in OPENROUTER_API_KEY
```

`HF_TOKEN` is optional (the dataset is not gated).

## Run

```bash
make data   # fetch the calls listed in data/manifest.csv into data/raw/ (gitignored)
make run    # extract all calls with the default model/prompt/sampling; prints a cost estimate first
make test   # unit tests (no network)
```

`python main.py run --help` lists the options: `--model` (from `config/models.yaml`), `--prompt` (`prompts/extract_<version>.md`), `--sampling` (`config/sampling.yaml`), `--split all|golden|dev`, `--runs N`, `--yes` to skip the confirmation.

Results go to `results/runs/<run_id>.jsonl`, one line per call and run, with model, prompt version and hash, sampling, status, latency, tokens, cost, code-check warnings, raw output and the parsed record.

## Layout

- `src/schema.py`: Pydantic QA record (`schema_version = "v1"`)
- `src/dataset.py`, `data/download.py`: call selection, manifest, transcript loading
- `src/clients/`: model interface, OpenRouter backend, retry/backoff
- `src/extract.py`: model call, schema validation, code checks (`src/checks.py`)
- `prompts/`: versioned prompts and `CHANGELOG.md`
- `config/`: models (prices, timeouts, retries) and sampling configs

Raw transcripts are CC BY-NC 4.0 and are not committed; `data/manifest.csv` records exactly which calls are used.
