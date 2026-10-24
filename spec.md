
# HW1 spec — Structured Extraction Service (Call QA & Compliance Copilot, stage 1)

Input spec for implementation. Source of truth: `Project spec.md` (the project being built) + the HW1 brief (`Домашні завдання _ 2 потік _ AI Engineering.pdf`) + lecturer guidance (`Overview.md`). Where this file proposes a default, it is marked **Default** and can be changed during brainstorming.

## 1. Goal
A Python service that turns raw, unlabelled call-centre transcripts into a validated JSON QA record, compares a paid provider model with a local model across prompt versions and sampling configs, and justifies one choice for production with measured numbers.

This is stage 1 of a 4-stage system (extraction → RAG → agent → API). Design so stage 2 (RAG with citations by call ID + timestamp) and stage 3 (QA agent with transcript quotes) can reuse the data loader, model interface and outputs.

## 2. The 4 steps of the brief, deadlines and grading
The HW1 brief splits the work into 4 steps. Build in this order; each step should run end to end before the next starts.

| Step | What it delivers | Spec sections | Brief's estimate |
|---|---|---|---|
| **Step 1 — Schema + baseline** | Pydantic schema; baseline prompt (v1); provider model via structured output with retry + timeout; all ≥ 30 calls run, results saved | §3, §4, §5 (provider), §6 (v1 only) | ≈ 2 h |
| **Step 2 — Second model + measurements** | Local model behind the same interface; sampling params in config, ≥ 2 configs; metrics on the golden set: per-field accuracy, % valid, latency p50/p95, cost per 1,000 calls | §5 (local), §7, §10, §11 | ≈ 2 h |
| **Step 3 — Prompt versioning + validation** | Prompts as versioned files with changelog (≥ 2 versions); schema validation + 1 repair attempt, then `failed`; model, prompt version and sampling logged per result | §6 (v2 + changelog), §8, §9 | ≈ 3 h |
| **Step 4 — Comparison report** | REPORT.md: model × prompt version × sampling table, 3–5 error analyses, production choice + when you'd change it | §12 | ≈ 2 h |

Deadlines:
- **Checkpoint = Steps 1 and 2 done:** 24.10, repo posted in #ai-engineering-2-flood. Not graded; feedback at the Q&A on 26.10.
- **Full submission = all 4 steps done:** **27.10, 23:59 Kyiv (22:59 Berlin)**, one GitHub repo link in the LMS.

Grading: 30 points. Most points come from Step 2 (measurements) and Step 3 (versioning + validation). Engineering approach and honest measurements are graded, not peak accuracy.
- Out of scope: UI, deployment, fine-tuning, large dataset, RAG, agent.

## 3. Data
**Source:** CallCenterEN (AIxBlock) — https://huggingface.co/datasets/AIxBlock/92k-real-world-call-center-scripts-english. One zip per domain; each call is AssemblyAI JSON with `text`, `confidence`, `audio_duration`, `words` (timestamps + confidence), `redacted_pii_policies`. PII already masked (`[PERSON_NAME]`, `[MONEY_AMOUNT]`, `[DATE]`, …). No speaker labels.

**Licence constraint (CC BY-NC 4.0, no redistribution):** raw transcripts are NOT committed. The brief requires `data/` with texts and golden set, so `data/` contains:
- `data/download.py` (or `make data`) — fetches the chosen domain zips and extracts only the selected calls. Check at implementation time whether the dataset is gated; if so, read `HF_TOKEN` from `.env`.
- `data/manifest.csv` — selected call IDs, domain, duration, split (golden / dev). Committed.
- `data/golden/golden_v1.jsonl` — hand labels (own work), keyed by call ID. Committed.
- `data/raw/` — downloaded transcripts, gitignored.
- `data/README.md` — dataset described by category (domains, counts, length distribution); lecturer accepts this.

**Selection.** **Default:** 3 domains — Medicare inbound, auto insurance, home services. ≥ 30 calls total, ~10–12 per domain, picked with a fixed seed; mix of lengths, including a few short/broken calls. 10 calls (≈ 4 Medicare, 3 auto, 3 home services) form the golden set; the remaining ≥ 20 are the dev set.

**Rules**
- Feed the transcript `text` raw, as delivered (no cleaning). Keep `words` on disk for stage 2 timestamps.
- Golden labels are made from the transcript only, never from model output. Labelling rules live in `data/golden/LABELING.md` and match the schema field descriptions.
- Golden set contains only what can be determined from the text. Versioned (`golden_v1`, `golden_v2`); compare runs only within one version.
- Prompt changes are written while looking at the dev set, not the golden set, so prompt v2 doesn't leak golden answers.
- Calls average ~7 min (~1–2k words); fit in context, no chunking needed. **Default:** log a warning and chunk only if a call exceeds the local model's context.

## 4. Schema (Pydantic, `schema_version = "v1"`)
Each field is described once with `Field(description=...)` and passed via structured output. Every enum has short per-value definitions in the description and includes `other`.

| Field | Type | Kind | Notes |
|---|---|---|---|
| `domain` | enum: medicare, auto_insurance, home_services, health_insurance, telecom, other | inferred | Ground truth is also known from the source zip → free accuracy check on all 30+ calls |
| `direction` | enum: inbound, outbound, unknown | inferred | |
| `customer_intent` | enum (see open question 1) + `other` | inferred | Scored per class |
| `outcome` | enum: sale, transfer, callback, not_interested, issue_resolved, other | inferred | `issue_resolved` added for service calls (open question 2); scored per class |
| `objections` | list of `{type: enum(price, already_covered, need_to_think, spouse_or_family, not_eligible, distrust, timing, other), handled: bool}` | extracted | Nested list (brief requirement). Empty list if none |
| `compliance` | object: `recording_disclosed: {value: bool \| null, evidence: str \| null}`, `disclaimer_before_benefits: {value: enum(yes, no, not_applicable), evidence: str \| null}` | extracted | Nested object. `not_applicable` when no benefits discussed or domain is not Medicare. `evidence` = short verbatim quote |
| `agent_handoff` | bool | extracted | Call passed to another agent mid-call |
| `next_action` | enum: none, callback_scheduled, transfer, send_documents, follow_up_contact, other + `next_action_note: str \| null` | inferred | Only the enum is scored; the note is not |

≥ 6 fields, ≥ 1 enum, ≥ 1 nested object/list: satisfied.

**Code checks (code verifies, model extracts)** — run after schema validation, logged as warnings, never silently fixed:
- every `evidence` quote fuzzy-matches the transcript (e.g. rapidfuzz partial ratio ≥ 90); otherwise flag `evidence_not_found`;
- `disclaimer_before_benefits != not_applicable` while predicted domain is not Medicare → flag;
- predicted `domain` vs source domain mismatch → flag.

## 5. Model interface
- One interface, e.g. `extract(transcript, prompt, sampling) -> ExtractionResult`, with two backends:
  - **Provider:** **Default:** OpenRouter via the OpenAI SDK (`OPENROUTER_API_KEY`), a cheap model with JSON-schema structured output. Exact model chosen in config.
  - **Local:** Ollama on the laptop. **Default:** a qwen3 model with thinking mode **off** (otherwise latency, tokens and JSON break). Structured output via Ollama's JSON-schema `format`.
- Same prompt and same schema-passing method for both models (fair comparison).
- Transport errors and timeouts: retry with exponential backoff (**Default:** 3 attempts, 60 s timeout provider / longer for local, configurable).
- Model list, prices per 1M tokens and timeouts in `config/models.yaml`.

## 6. Prompts
- `prompts/extract_v1.md`, `prompts/extract_v2.md`, `prompts/CHANGELOG.md` (what changed, why, which dev-set errors motivated it).
- Prompt covers only what the schema can't: when to use null / `unknown` / `not_applicable`, inferring agent vs customer without speaker labels, handling ASR errors, multiple agents, what counts as "benefits discussed".
- Prompt version and file hash logged with every result.

## 7. Sampling configs
`config/sampling.yaml`, ≥ 2 configs. **Default:** `deterministic` (temperature 0, top_p 1) and `low` (temperature 0.3, top_p 0.9). Seed set where the backend supports it.

## 8. Validation and repair
1. Parse + validate against the Pydantic schema.
2. If invalid: exactly one repair call (previous output + validation error), then validate again.
3. Still invalid → status `failed`; raw output kept.
Status per result: `valid_first_try` | `valid_after_repair` | `failed`.

## 9. Logging (`results/`)
One JSONL line per (call × model × prompt version × sampling × run):
`run_id, timestamp, call_id, split, model, provider, prompt_version, prompt_hash, schema_version, sampling_name, temperature, top_p, run_idx, status, latency_ms, input_tokens, output_tokens, cost_usd, warnings[], raw_output, parsed`.
Results are committed (outputs contain only already-masked derived data — re-check before committing).

## 10. Experiment matrix
2 models × 2 prompt versions × 2 sampling configs.
- All 30+ calls: 1 run per combination (validity, latency, cost).
- Golden 10: 3–5 runs per combination; report medians (accuracy, latency).
- Budget: ≤ $5 API total; estimate cost before a full run and print it. Local model must run on an ordinary laptop — **Default:** if local runs are too slow, cut repeated runs to the golden set only and note it in REPORT.md.

## 11. Metrics (`eval.py`)
Computed against `golden_v1`, per combination:
- **Per-field accuracy**: exact match for enums/bools; `objections` → precision/recall/F1 on types + `handled` accuracy on matched types; `compliance.*.value` exact match (evidence checked by code, not scored vs golden).
- **Extracted vs inferred** fields reported separately; inferred enums also as **per-class accuracy**.
- `domain` accuracy also on all 30+ calls against source metadata.
- **% valid**: first try / after repair / failed.
- **Latency p50 / p95** per call.
- **Cost per 1,000 calls**: from provider usage or tokens × config price; local = $0 API cost (note hardware in report).
- Output: `results/metrics.csv` + a markdown table pasted into REPORT.md.

## 12. REPORT.md
- Table: model × prompt version × sampling with all metrics above.
- 3–5 error analyses: what was predicted instead of what, and why (expected candidates: agent/customer confusion without speaker labels, ASR errors on product names, handoffs, disclaimer timing).
- Production choice in one paragraph + conditions that would change it (volume, cost, latency, data-residency/self-hosting needs).

## 13. Repo layout and commands
```
.
├── main.py                # one-command entry: data check → runs → eval → metrics
├── Makefile               # make data / make run / make eval / make test
├── src/                   # schema.py, clients/ (provider, local), extract.py, validate.py, checks.py, eval.py
├── config/                # models.yaml, sampling.yaml
├── prompts/               # extract_v1.md, extract_v2.md, CHANGELOG.md
├── data/                  # download.py, manifest.csv, golden/, README.md (raw/ gitignored)
├── results/               # runs/*.jsonl, metrics.csv
├── tests/                 # schema, repair path, scoring, code checks
├── REPORT.md
├── README.md              # install (Python 3.11+, Ollama + model pull), .env setup, run
├── .env.example           # OPENROUTER_API_KEY, HF_TOKEN (if needed), OLLAMA_HOST
└── .gitignore             # .env, data/raw/
```
`make run` (or `python main.py`) runs end to end on a fresh clone after `.env` is filled and Ollama is running.

## 14. Acceptance criteria (rubric, grouped by step)
**Step 1**
- [ ] Schema: ≥ 6 fields, enum, nested structure, `Field(description=...)`
- [ ] Provider model via structured output, with retry and timeout
- [ ] All ≥ 30 calls run, results saved

**Step 2**
- [ ] Local model behind the same interface
- [ ] Sampling in config, ≥ 2 configs compared
- [ ] Accuracy, validity, latency p50/p95, cost per 1,000 correctly measured

**Step 3**
- [ ] ≥ 2 prompt versions with changelog explaining changes
- [ ] Schema validation + one repair attempt + `failed`
- [ ] Model, prompt version and sampling logged per result

**Step 4**
- [ ] REPORT.md: full comparison table, 3–5 error analyses, justified choice

**Repo quality (all steps)**
- [ ] README, one-command run, keys only in `.env`, raw data not committed

## 15. Stretch (no extra points, only if time)
Third cheap provider model · automated regression run of prompts on the golden set · response cache keyed by (call, model, prompt hash, sampling).

## 16. Open questions for brainstorming
1. Final `customer_intent` enum — decide after reading ~10 dev calls per domain (candidates: enroll_or_buy, plan_or_quote_info, billing, claim, cancel, service_appointment, technical_support, complaint, other).
2. Keep `issue_resolved` in `outcome`, or limit the domains to sales calls only?
3. Exact provider model and local model size (depends on laptop RAM and OpenRouter prices).
4. Repo visibility: public repo with labels + call IDs only, or private repo shared with the lecturer/mentor?
