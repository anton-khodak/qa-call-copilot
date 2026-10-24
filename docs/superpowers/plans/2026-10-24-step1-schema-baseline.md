# Step 1 — Schema + Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn ≥ 30 raw CallCenterEN transcripts into Pydantic-validated QA records with one OpenRouter model and prompt v1, and save one JSONL result line per call.

**Architecture:** `data/download.py` reads only the selected calls out of the remote HF zips via HTTP range reads and writes a committed `manifest.csv`. `src/` holds the schema, the dataset loader, a provider client behind a `ModelClient` protocol (the Ollama client in Step 2 implements the same protocol), the `extract()` pipeline (call model → validate → code checks), and a JSONL result writer that already uses the §9 record shape, so Steps 2–3 add fields' *values*, not a new format. `main.py run` ties these together.

**Tech Stack:** Python 3.11+ (managed with `uv`), Pydantic v2, `openai` SDK pointed at OpenRouter, `huggingface_hub` (HfFileSystem), `rapidfuzz`, `PyYAML`, `python-dotenv`, `pytest`.

**Spec:** `spec.md` (Step 1 = §3, §4, §5 provider, §6 v1; §9 record shape used early).

## Global Constraints

- Python 3.11+ (the system `python3` is 3.9.6, so use `uv`-managed 3.11).
- Raw transcripts are never committed: `data/raw/` and `.env` are gitignored.
- Keys only in `.env`: `OPENROUTER_API_KEY`, `HF_TOKEN` (optional, the dataset is **not gated**, checked 2026-10-24), `OLLAMA_HOST`.
- `schema_version = "v1"`. Every field has `Field(description=...)`; every enum includes `other` and has short per-value definitions in its description.
- Transcript `text` goes to the model raw, as delivered. No cleaning.
- Retry transport errors/timeouts with exponential backoff: 3 attempts, 60 s timeout for the provider, both set in `config/models.yaml`.
- Code checks only add warnings. They never change model output.
- Selection seed: `42`. Golden split: 4 Medicare, 3 auto insurance, 3 home services. Everything else is dev.
- Budget: ≤ $5 API total. Print the cost estimate before every run.

## Decisions made for this plan (from spec §16 open questions)

- **`customer_intent` v1 enum** = the spec's candidate list: `enroll_or_buy, plan_or_quote_info, billing, claim, cancel, service_appointment, technical_support, complaint, other`. Revisit after reading dev calls. Any change bumps `schema_version`.
- **`outcome`** keeps `issue_resolved` (spec default).
- **Provider model:** `openai/gpt-4o-mini` on OpenRouter, $0.15 / $0.60 per 1M in/out tokens. Task 5 includes a step to confirm the id and prices against the live OpenRouter model list before the first paid call.
- **Source zips:** `medicare_inbound.zip` → `medicare`, `auto_insurance_customer_service_inbound.zip` → `auto_insurance`, `home_service_inbound.zip` → `home_services`. Members look like `<dir>/<stamp>_<uuid>_<hash>_transcript.json`. Skip `__MACOSX/` entries. `call_id` = the basename without `_transcript.json`.
- **Prompt layout:** the prompt file is the system message. The user message is the transcript wrapped in `<transcript>…</transcript>`. `prompt_hash` = the first 12 hex characters of the sha256 of the file bytes.
- **Step 1 statuses:** `valid_first_try` or `failed` (the repair path arrives in Step 3). A transport failure after all retries gives `failed` plus the warning `transport_error:<ExceptionName>`.
- **Latency** = wall-clock time across all attempts for that call.

## Review Focus

1. **Fresh clone with a committed manifest:** `download.py` must fetch exactly the calls in `manifest.csv` and must not select new ones. Reselecting only happens with `--reselect`. Test in Task 2.
2. **Model output that is not schema-valid** (an enum value outside the list, `content=None`/refusal, prose instead of JSON): record `failed`, keep `raw_output`, carry on with the next call. Test in Task 6.
3. **Provider timeout on all 3 attempts:** one `failed` record with a `transport_error` warning. The run keeps going. Non-retryable 400 errors are not retried. Tests in Tasks 5 and 6.
4. **Evidence quotes that differ from the transcript in case, whitespace or punctuation** still match. A `null` evidence never gets flagged. Tests in Task 3.
5. **Missing `OPENROUTER_API_KEY`:** fail fast with a clear message before any call, not 36 failed records. Test in Task 7.

---

### Task 1: Project scaffold + schema

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `Makefile`, `src/__init__.py`, `src/schema.py`
- Test: `tests/test_schema.py`

**Interfaces:**
- Produces: `src.schema.SCHEMA_VERSION = "v1"`; `CallQARecord` (Pydantic, `extra="forbid"` on every model, no defaults so every key is required); nested `Objection(type: ObjectionType, handled: bool)`, `Compliance(recording_disclosed: RecordingDisclosed, disclaimer_before_benefits: DisclaimerBeforeBenefits)`, `RecordingDisclosed(value: bool | None, evidence: str | None)`, `DisclaimerBeforeBenefits(value: DisclaimerValue, evidence: str | None)`; `str` enums `Domain, Direction, CustomerIntent, Outcome, ObjectionType, DisclaimerValue, NextAction` with the values in spec §4 and the intent list above; top-level fields `domain, direction, customer_intent, outcome, objections: list[Objection], compliance, agent_handoff: bool, next_action, next_action_note: str | None`; `strict_json_schema() -> dict`, the JSON schema sent as structured output to both backends.

- [ ] **Step 1: Set up the toolchain**

Run: `brew install uv && uv init --no-readme --python 3.11 && git init`. Edit `pyproject.toml`: dependencies `pydantic>=2.7, openai>=1.40, huggingface_hub>=0.24, rapidfuzz>=3, pyyaml, python-dotenv`, dev group `pytest`, `[tool.pytest.ini_options] markers = ["live: hits a real API"]`, `addopts = "-m 'not live'"`. `.gitignore`: `.env, data/raw/, .venv/, __pycache__/`. `.env.example`: `OPENROUTER_API_KEY=`, `HF_TOKEN=`, `OLLAMA_HOST=http://localhost:11434`. Makefile targets: `data` (`uv run python data/download.py`), `run` (`uv run python main.py run`), `test` (`uv run pytest`).
Run: `uv sync && uv run python --version`. Expected: `Python 3.11.x` or later.

- [ ] **Step 2: Write the failing tests**

```python
from src.schema import CallQARecord, strict_json_schema, SCHEMA_VERSION
import pydantic, pytest

VALID = {
    "domain": "medicare", "direction": "inbound", "customer_intent": "enroll_or_buy",
    "outcome": "transfer", "objections": [{"type": "price", "handled": True}],
    "compliance": {"recording_disclosed": {"value": True, "evidence": "this call is recorded"},
                   "disclaimer_before_benefits": {"value": "not_applicable", "evidence": None}},
    "agent_handoff": True, "next_action": "transfer", "next_action_note": None,
}

def test_valid_record_parses(): assert CallQARecord.model_validate(VALID).domain.value == "medicare"
def test_unknown_enum_rejected():
    with pytest.raises(pydantic.ValidationError): CallQARecord.model_validate({**VALID, "outcome": "maybe"})
def test_extra_key_rejected():
    with pytest.raises(pydantic.ValidationError): CallQARecord.model_validate({**VALID, "foo": 1})
def test_every_enum_has_other_except_fixed_ones():
    # Direction uses `unknown` and DisclaimerValue uses `not_applicable` (spec §4); all others include `other`
def test_every_field_has_description():  # walk model_fields of every model, assert .description
def test_strict_schema_shape():
    # every "type": "object" node (incl. $defs) has additionalProperties False and required == list(properties)
def test_schema_version(): assert SCHEMA_VERSION == "v1"
```

- [ ] **Step 3: Run to verify they fail**

Run: `uv run pytest tests/test_schema.py -v`. Expected: ImportError on `src.schema`.

- [ ] **Step 4: Implement `src/schema.py`**

Each enum's per-value definitions go in the description of the field that uses it, e.g. `"transfer: call handed to another agent/department; callback: …"`. The `outcome` and `next_action` descriptions must spell out the difference between `transfer` (outcome) and `agent_handoff` (bool). `strict_json_schema()` returns `CallQARecord.model_json_schema()`. With `extra="forbid"` and no defaults it already meets OpenAI strict mode, and the test proves that. Do not post-process the schema unless the test fails.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_schema.py -v`. Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock .gitignore .env.example Makefile src/ tests/test_schema.py spec.md CLAUDE.md
git commit -m "feat: project scaffold and v1 QA record schema"
```

---

### Task 2: Data selection, download and loader

**Files:**
- Create: `src/dataset.py`, `data/download.py`
- Test: `tests/test_dataset.py`

**Interfaces:**
- Produces (`src/dataset.py`):
  - `DOMAIN_ZIPS: dict[str, str]` (domain → zip filename, see Decisions); `REPO_ID = "AIxBlock/92k-real-world-call-center-scripts-english"`.
  - `call_id_from_member(member: str) -> str | None`. Returns `None` for `__MACOSX` entries and for anything that is not `*_transcript.json`.
  - `select_members(members: list[tuple[str, int]], n: int = 12, seed: int = 42) -> list[tuple[str, int]]`. Input is `(member, uncompressed_size)`. Sort by size, cut into 4 quartile bins, take `n // 4` from each with `random.Random(seed)`. File size stands in for call length, so the selection covers all lengths, short and broken calls included, without downloading anything.
  - `assign_splits(rows: list[ManifestRow], golden_counts: dict[str, int] = {"medicare": 4, "auto_insurance": 3, "home_services": 3}, seed: int = 42) -> list[ManifestRow]`
  - `@dataclass ManifestRow(call_id, domain, zip_name, member, file_size: int, audio_duration: float | None, word_count: int | None, split: str)`
  - `read_manifest(path) -> list[ManifestRow]`, `write_manifest(path, rows)`
  - `@dataclass Transcript(call_id, domain, split, text: str, audio_duration: float, words: list[dict])`
  - `load_transcript(row: ManifestRow, raw_dir: Path = Path("data/raw")) -> Transcript`. Reads `data/raw/<domain>/<call_id>.json`.
  - `load_calls(split: str = "all", manifest=Path("data/manifest.csv")) -> list[Transcript]`. `split` is `all | golden | dev`.
- Produces (`data/download.py`): CLI `python data/download.py [--reselect]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_call_id_from_member():
    m = "auto_insurance_customer_service_inbound/2020-07-17-14-44-38_318178f6-bb02_v2fH_transcript.json"
    assert call_id_from_member(m) == "2020-07-17-14-44-38_318178f6-bb02_v2fH"
    assert call_id_from_member("__MACOSX/auto/._x_transcript.json") is None
    assert call_id_from_member("auto/") is None

def test_select_members_deterministic_and_spans_quartiles():
    members = [(f"d/c{i}_transcript.json", i * 100) for i in range(200)]
    a, b = select_members(members, 12, 42), select_members(members, 12, 42)
    assert a == b and len(a) == 12
    sizes = sorted(s for _, s in a)
    assert sizes[0] < 5000 and sizes[-1] > 15000   # smallest and largest quartile both present

def test_assign_splits_counts():  # 12 rows per domain → golden 4/3/3, rest dev, deterministic for seed 42

def test_manifest_roundtrip(tmp_path):  # write_manifest then read_manifest gives equal rows (ints/None preserved)

def test_load_transcript_keeps_text_raw(tmp_path):
    # write {"text": "  Hi [PERSON_NAME]..  ", "audio_duration": 12, "words": [...], ...}
    # assert t.text == "  Hi [PERSON_NAME]..  "  (no strip, no cleaning)

def test_load_transcript_empty_text_ok(tmp_path):  # text "" loads as "" without raising

def test_download_uses_existing_manifest(tmp_path, monkeypatch):
    # manifest with 2 rows exists; patch the HF opener with a fake that records which members were read
    # run download.main([]) → exactly those 2 members fetched, select_members not called
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_dataset.py -v`. Expected: ImportError.

- [ ] **Step 3: Implement `src/dataset.py` and `data/download.py`**

`download.py` opens each zip with `HfFileSystem().open(f"datasets/{REPO_ID}/{zip_name}", "rb")` and passes it to `zipfile.ZipFile`. That makes HTTP range reads, so only the central directory and the chosen members are fetched (Medicare is 826 MB). Pass `token=os.getenv("HF_TOKEN")` (None is fine). If `data/manifest.csv` exists and there is no `--reselect`, fetch the listed members and skip files already in `data/raw/`. Otherwise list members, `select_members`, extract, fill `audio_duration`/`word_count` from the JSON, `assign_splits`, `write_manifest`. Print per-domain counts (members available, selected, golden). Keep the opener behind a function (`open_zip(zip_name) -> zipfile.ZipFile`) so the test can patch it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_dataset.py -v`. Expected: 7 passed.

- [ ] **Step 5: Run the real download**

Run: `make data`. Expected: 36 rows in `data/manifest.csv` (12 per domain, 10 golden), 36 files under `data/raw/`, and `git status` does not show `data/raw/`. Run it a second time. Expected: no new downloads, manifest unchanged (`git diff --stat data/manifest.csv` empty after the first commit).

- [ ] **Step 6: Commit**

```bash
git add src/dataset.py data/download.py data/manifest.csv tests/test_dataset.py
git commit -m "feat: seeded call selection, range-read download, transcript loader"
```

---

### Task 3: Code checks

**Files:**
- Create: `src/checks.py`
- Test: `tests/test_checks.py`

**Interfaces:**
- Consumes: `CallQARecord` (Task 1).
- Produces: `run_checks(record: CallQARecord, transcript: str, source_domain: str) -> list[str]`. Possible warnings: `evidence_not_found:recording_disclosed`, `evidence_not_found:disclaimer_before_benefits`, `disclaimer_not_medicare`, `domain_mismatch:predicted=<x>,source=<y>`. Also `evidence_matches(quote: str, transcript: str, threshold: int = 90) -> bool`.

- [ ] **Step 1: Write the failing tests**

```python
T = "Hi, this call may be recorded for quality and training purposes. How can I help?"
def test_exact_quote_matches(): assert evidence_matches("this call may be recorded", T)
def test_case_space_punct_tolerant(): assert evidence_matches("This call  may be RECORDED,", T)
def test_invented_quote_flagged(): assert not evidence_matches("you agree to our terms of service", T)
def test_null_evidence_no_flag():  # recording_disclosed.evidence None → no evidence_not_found warning
def test_disclaimer_on_non_medicare_flagged():  # predicted domain auto_insurance, disclaimer "yes" → "disclaimer_not_medicare"
def test_domain_mismatch_flagged():  # predicted home_services, source medicare → "domain_mismatch:predicted=home_services,source=medicare"
def test_clean_record_no_warnings():
def test_checks_do_not_mutate_record():  # model_dump before == after
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_checks.py -v`. Expected: ImportError.

- [ ] **Step 3: Implement `src/checks.py`**

Normalise both strings first (lowercase, strip punctuation, collapse whitespace), then `rapidfuzz.fuzz.partial_ratio(quote, transcript) >= threshold`. An empty quote after normalising counts as not found.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_checks.py -v`. Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/checks.py tests/test_checks.py
git commit -m "feat: code checks for evidence quotes and domain consistency"
```

---

### Task 4: Prompt v1 + configs

**Files:**
- Create: `prompts/extract_v1.md`, `prompts/CHANGELOG.md`, `src/prompts.py`, `config/models.yaml`, `config/sampling.yaml`, `src/config.py`
- Test: `tests/test_prompts_config.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) Prompt(version: str, text: str, hash: str)`; `load_prompt(version: str, prompts_dir=Path("prompts")) -> Prompt`; `build_user_message(transcript: str) -> str` returns `"<transcript>\n" + transcript + "\n</transcript>"`.
  - `@dataclass(frozen=True) ModelConfig(name, provider, model_id, base_url, price_input_per_1m: float, price_output_per_1m: float, timeout_s: float, max_attempts: int)`; `load_model(name: str, path=Path("config/models.yaml")) -> ModelConfig`.
  - `@dataclass(frozen=True) SamplingConfig(name, temperature: float, top_p: float, seed: int | None)`; `load_sampling(name: str, path=Path("config/sampling.yaml")) -> SamplingConfig`.

- [ ] **Step 1: Write the failing tests**

```python
def test_prompt_hash_stable_and_short():
    p = load_prompt("v1"); assert p.version == "v1" and len(p.hash) == 12 and p.hash == load_prompt("v1").hash
def test_prompt_hash_changes_with_text(tmp_path):  # two files differing by one char → different hash
def test_prompt_v1_covers_required_topics():
    t = load_prompt("v1").text.lower()
    for kw in ["null", "unknown", "not_applicable", "speaker", "asr", "benefits", "verbatim"]: assert kw in t
def test_user_message_wraps_raw(): assert build_user_message(" a ") == "<transcript>\n a \n</transcript>"
def test_load_model():
    m = load_model("gpt4o_mini"); assert m.provider == "openrouter" and m.timeout_s == 60 and m.max_attempts == 3
def test_load_sampling(): s = load_sampling("deterministic"); assert (s.temperature, s.top_p, s.seed) == (0.0, 1.0, 42)
def test_unknown_name_raises_keyerror_listing_options():
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_prompts_config.py -v`. Expected: ImportError.

- [ ] **Step 3: Write `prompts/extract_v1.md`**

Cover only what the schema can't (spec §6), one short section each: the task and output (one JSON QA record, transcript only); null / `unknown` / `not_applicable` rules; telling agent from customer without speaker labels (the agent greets with the company, asks qualifying questions, mentions recording/disclaimers); ASR errors and `[PII]` placeholders are normal, so don't "fix" them; multiple agents or transfers (`agent_handoff` vs `outcome=transfer`); what counts as "benefits discussed" for Medicare; `evidence` must be a short verbatim quote copied from the transcript, or null. `CHANGELOG.md`: a `## v1 — 2026-10-24` baseline entry.

- [ ] **Step 4: Write configs and loaders**

`config/models.yaml`, under the top-level key `models:`: `gpt4o_mini: {provider: openrouter, model_id: openai/gpt-4o-mini, base_url: https://openrouter.ai/api/v1, price_input_per_1m: 0.15, price_output_per_1m: 0.60, timeout_s: 60, max_attempts: 3}`. `config/sampling.yaml`, under `sampling:`: `deterministic: {temperature: 0.0, top_p: 1.0, seed: 42}` (Step 2 adds `low`). `load_prompt` hashes the bytes it read.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_prompts_config.py -v`. Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add prompts/ config/ src/prompts.py src/config.py tests/test_prompts_config.py
git commit -m "feat: prompt v1, model and sampling configs"
```

---

### Task 5: Provider client with retry + timeout

**Files:**
- Create: `src/clients/__init__.py`, `src/clients/base.py`, `src/clients/retry.py`, `src/clients/provider.py`
- Test: `tests/test_provider_client.py`

**Interfaces:**
- Consumes: `ModelConfig`, `SamplingConfig` (Task 4); `strict_json_schema()` (Task 1).
- Produces:
  - `base.py`: `@dataclass Completion(text: str | None, input_tokens: int, output_tokens: int)`; `class TransportError(Exception)` (wraps the last exception and keeps `attempts: int`); `class ModelClient(Protocol): config: ModelConfig; def complete(self, system: str, user: str, schema: dict, sampling: SamplingConfig) -> Completion`.
  - `retry.py`: `call_with_retry(fn: Callable[[], T], max_attempts: int, retry_on: tuple[type[BaseException], ...], base_delay_s: float = 1.0, sleep: Callable[[float], None] = time.sleep) -> T`. Waits `base_delay_s * 2**i` between attempts. Once attempts run out it raises `TransportError`. Exceptions not in `retry_on` propagate immediately.
  - `provider.py`: `ProviderClient(config: ModelConfig, api_key: str, sdk: openai.OpenAI | None = None)` implements `ModelClient`. `RETRYABLE = (openai.APITimeoutError, openai.APIConnectionError, openai.RateLimitError, openai.InternalServerError)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_retry_succeeds_on_third_attempt():
    calls, sleeps = [], []
    def fn():
        calls.append(1)
        if len(calls) < 3: raise TimeoutError()
        return "ok"
    assert call_with_retry(fn, 3, (TimeoutError,), sleep=sleeps.append) == "ok" and sleeps == [1.0, 2.0]
def test_retry_exhausted_raises_transport_error():  # always TimeoutError → TransportError, attempts == 3
def test_non_retryable_propagates_immediately():    # ValueError → raised after 1 call, no sleeps

def test_provider_request_shape():
    fake = FakeSDK(content='{"x":1}', prompt_tokens=1200, completion_tokens=150)
    c = ProviderClient(load_model("gpt4o_mini"), "k", sdk=fake)
    out = c.complete("SYS", "USER", {"type": "object"}, load_sampling("deterministic"))
    kw = fake.last_kwargs
    assert kw["model"] == "openai/gpt-4o-mini" and kw["temperature"] == 0.0 and kw["top_p"] == 1.0 and kw["seed"] == 42
    assert kw["timeout"] == 60
    assert kw["response_format"]["type"] == "json_schema" and kw["response_format"]["json_schema"]["strict"] is True
    assert kw["messages"] == [{"role": "system", "content": "SYS"}, {"role": "user", "content": "USER"}]
    assert (out.text, out.input_tokens, out.output_tokens) == ('{"x":1}', 1200, 150)
def test_provider_retries_timeouts():          # FakeSDK raises openai.APITimeoutError twice then succeeds → Completion
def test_provider_none_content_returned_as_none():  # refusal / content=None → Completion(text=None, ...) without raising

@pytest.mark.live
def test_live_smoke():  # skip unless OPENROUTER_API_KEY; tiny schema, assert out.text parses as JSON
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_provider_client.py -v`. Expected: ImportError.

- [ ] **Step 3: Implement the client**

Build the default SDK as `openai.OpenAI(base_url=config.base_url, api_key=api_key, max_retries=0)`. The SDK's built-in retries are off so `call_with_retry` owns them. Call `sdk.chat.completions.create(..., timeout=config.timeout_s, response_format={"type": "json_schema", "json_schema": {"name": "call_qa_record", "strict": True, "schema": schema}})`. Missing `usage` → tokens 0.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_provider_client.py -v`. Expected: 6 passed, 1 deselected.

- [ ] **Step 5: Confirm model id and prices, then live smoke**

Run: `curl -s https://openrouter.ai/api/v1/models | uv run python -c "import sys,json; m=[x for x in json.load(sys.stdin)['data'] if x['id']=='openai/gpt-4o-mini'][0]; print(m['pricing'], 'structured_outputs' in m.get('supported_parameters', []))"`
Expected: the model exists with `structured_outputs` True. Copy the prompt/completion prices (per token × 1e6) into `config/models.yaml` if they differ. If the model is gone, choose the cheapest model that supports `structured_outputs` and record it in `models.yaml`.
Run: `cp .env.example .env` (fill in the key), then `uv run pytest -m live -v`. Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add src/clients/ tests/test_provider_client.py config/models.yaml
git commit -m "feat: OpenRouter structured-output client with retry and timeout"
```

---

### Task 6: Extraction pipeline + result log

**Files:**
- Create: `src/extract.py`, `src/results.py`
- Test: `tests/test_extract.py`

**Interfaces:**
- Consumes: `ModelClient`, `Completion`, `TransportError` (Task 5); `Prompt`, `build_user_message` (Task 4); `CallQARecord`, `strict_json_schema`, `SCHEMA_VERSION` (Task 1); `run_checks` (Task 3); `Transcript` (Task 2).
- Produces:
  - `@dataclass ExtractionResult(status: Literal["valid_first_try", "valid_after_repair", "failed"], parsed: dict | None, raw_output: str | None, warnings: list[str], latency_ms: int, input_tokens: int, output_tokens: int)`
  - `extract(client: ModelClient, transcript: Transcript, prompt: Prompt, sampling: SamplingConfig) -> ExtractionResult`. It never raises for model or transport problems.
  - `results.py`: `cost_usd(input_tokens: int, output_tokens: int, model: ModelConfig) -> float`; `build_record(run_id, transcript, client_cfg: ModelConfig, prompt, sampling, run_idx: int, result: ExtractionResult) -> dict`, which returns exactly the 21 §9 keys in §9 order (`provider` = `ModelConfig.provider`, `model` = `model_id`, `timestamp` = UTC ISO-8601); `append_jsonl(path: Path, record: dict) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
# FakeClient(responses) returns/raises items in order; config = load_model("gpt4o_mini")
def test_valid_output():          # valid JSON → status valid_first_try, parsed == model_dump(mode="json"), latency_ms >= 0
def test_invalid_enum_failed():   # outcome "maybe" → failed, parsed None, raw_output kept, warning starts "validation_error"
def test_prose_output_failed():   # "Sure! Here is..." → failed, raw_output kept
def test_none_content_failed():   # Completion(text=None) → failed, warning "empty_output"
def test_transport_error_failed():# client raises TransportError → failed, raw_output None, warning "transport_error:APITimeoutError"
def test_bad_request_failed():    # client raises openai.BadRequestError → failed, warning "request_error:BadRequestError"
def test_checks_appended():       # valid output, domain differs from transcript.domain → "domain_mismatch:..." in warnings
def test_cost():                  assert cost_usd(1_000_000, 1_000_000, cfg) == pytest.approx(0.75)
def test_record_keys_match_spec():
    keys = ["run_id","timestamp","call_id","split","model","provider","prompt_version","prompt_hash",
            "schema_version","sampling_name","temperature","top_p","run_idx","status","latency_ms",
            "input_tokens","output_tokens","cost_usd","warnings","raw_output","parsed"]
    assert list(build_record(...).keys()) == keys
def test_append_jsonl(tmp_path):  # two appends → two lines, each json.loads-able
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_extract.py -v`. Expected: ImportError.

- [ ] **Step 3: Implement `extract` and `results.py`**

`extract`: time `client.complete(prompt.text, build_user_message(transcript.text), strict_json_schema(), sampling)` with `time.perf_counter`. If the text is non-empty, `CallQARecord.model_validate_json`, then `run_checks(record, transcript.text, transcript.domain)`. Catch `TransportError` and `openai.APIStatusError`. The validation warning is `validation_error:` plus the first error's `loc` and `msg`. Step 3 of the brief will add the repair call at this exact point, so keep validation in a separate helper: `validate_output(raw: str | None) -> tuple[CallQARecord | None, str | None]` (record, error).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_extract.py -v`. Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add src/extract.py src/results.py tests/test_extract.py
git commit -m "feat: extraction pipeline and spec-shaped JSONL results"
```

---

### Task 7: `main.py run` + full baseline run

**Files:**
- Create: `main.py`, `README.md`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: everything above.
- Produces: CLI `python main.py run --model gpt4o_mini --prompt v1 --sampling deterministic --split all --runs 1 [--yes] [--out-dir results/runs]` (the values shown are the defaults). Writes `<out-dir>/<run_id>.jsonl` with `run_id = f"{utc:%Y%m%dT%H%M%SZ}_{model}_{prompt}_{sampling}"`. `estimate_cost(transcripts: list[Transcript], model: ModelConfig, runs: int, prompt: Prompt, output_tokens: int = 400) -> float`, where input tokens ≈ `(len(prompt.text) + len(text)) / 4`. `make_client(model: ModelConfig) -> ModelClient` raises `SystemExit` naming the env var when the key is missing.

- [ ] **Step 1: Write the failing tests**

```python
def test_missing_key_exits_before_any_call(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="OPENROUTER_API_KEY"): make_client(load_model("gpt4o_mini"))
def test_estimate_cost():  # 2 transcripts of 4000 chars, empty prompt, runs=1 → (2*1000*0.15 + 2*400*0.60)/1e6
def test_run_writes_one_line_per_call(tmp_path, monkeypatch):
    # patch make_client → FakeClient (one valid, one TransportError) and load_calls → 2 transcripts
    # main(["run", "--yes", "--out-dir", str(tmp_path)]) → 1 file, 2 lines, statuses {"valid_first_try","failed"}
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_main.py -v`. Expected: ImportError.

- [ ] **Step 3: Implement `main.py` and `README.md`**

`main.py`: load `.env` with `python-dotenv`, use `argparse` subcommands (Step 2 adds `eval`), and check that `data/raw` holds every manifest file (otherwise exit with "run `make data`"). Print the cost estimate and ask for confirmation unless `--yes`. Loop calls × runs and print one progress line per call (`call_id status latency_ms`). Print a summary at the end: counts per status, total cost, output path. README: install (`brew install uv`, `uv sync`), `.env` setup, `make data`, `make run`, `make test`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v`. Expected: all tests pass (the live test is deselected).

- [ ] **Step 5: Run the baseline on all calls**

Run: `make run`. Expected: the estimate prints first (well under $0.10 for 36 calls). The JSONL has 36 lines, and most lines are `valid_first_try`. Check this with `uv run python -c "import json,collections,glob; f=sorted(glob.glob('results/runs/*.jsonl'))[-1]; print(collections.Counter(json.loads(l)['status'] for l in open(f)))"`. Read 3 records by hand to sanity-check the fields.

- [ ] **Step 6: PII re-check and commit**

Run: `grep -nE '[A-Z][a-z]+ [A-Z][a-z]+|[0-9]{3}[-. ][0-9]{3}[-. ][0-9]{4}' results/runs/*.jsonl | head`. Review the hits by hand for any unmasked names or phone numbers before committing (spec §9).

```bash
git add main.py README.md tests/test_main.py results/runs/
git commit -m "feat: one-command baseline run; results for all calls with gpt-4o-mini + prompt v1"
```

---

### Task 8: Golden-set scaffolding + data README

**Files:**
- Create: `src/golden.py`, `data/golden/LABELING.md`, `data/golden/golden_v1.jsonl`, `data/README.md`
- Test: `tests/test_golden.py`

**Interfaces:**
- Consumes: `CallQARecord` (Task 1), `read_manifest` (Task 2).
- Produces: `load_golden(path: Path = Path("data/golden/golden_v1.jsonl")) -> dict[str, CallQARecord]`. Each line is `{"call_id": ..., "label": {...CallQARecord...}}`. Raises `ValueError` on a duplicate `call_id` or on a `call_id` that is not a `golden` row in the manifest. Step 2's `eval.py` uses this.

- [ ] **Step 1: Write the failing tests**

```python
def test_load_golden_valid(tmp_path):        # 1 line for a golden manifest row → dict with that key, CallQARecord value
def test_duplicate_call_id_rejected(tmp_path):
def test_non_golden_call_id_rejected(tmp_path):  # id present in manifest but split dev → ValueError
def test_invalid_label_rejected(tmp_path):   # bad enum → pydantic.ValidationError
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_golden.py -v`. Expected: ImportError.

- [ ] **Step 3: Implement `src/golden.py`, write `LABELING.md` and `data/README.md`**

`LABELING.md`: one rule per schema field, using the same wording as the `Field(description=...)` text. It says labels come from the transcript only, never from model output, and that only text-determinable facts are labelled. `data/README.md`: source + licence (CC BY-NC 4.0, no redistribution), the 3 domains, counts per split, the length distribution from the manifest (min / median / max `audio_duration` and `word_count` per domain), and how to reproduce with `make data`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -v`. Expected: all pass.

- [ ] **Step 5: Hand-label the 10 golden calls (human task)**

The user reads each golden transcript under `data/raw/` and writes one line per call to `data/golden/golden_v1.jsonl`, without opening the model's results for those calls. Run: `uv run python -c "from src.golden import load_golden; print(len(load_golden()))"`. Expected: `10`.

- [ ] **Step 6: Commit**

```bash
git add src/golden.py tests/test_golden.py data/golden/ data/README.md
git commit -m "feat: golden_v1 labels, labelling rules and dataset description"
```
