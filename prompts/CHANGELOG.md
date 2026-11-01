# Prompt changelog

## v2 — 2026-11-01
v1 plus four sections, one per error class seen with v1 on the **26 dev calls** (deterministic runs of all three models). No golden transcript, golden error or golden per-field score was used.
- **"Who started the call" (`direction`).** gpt-4o-mini answered `inbound` on 16 of the 18 outbound-campaign dev calls (qwen3:8b 4, qwen3:14b 5). The openings are unambiguous ("the purpose of my call is…", "I'm calling you from…", "the one who called you a while ago", or the customer answering "Hello?"), so v2 lists these cues.
- **"Call type" (`call_type`).** Inbound plan-sales calls, where a screener passes on a customer "interested in Medicare Part C additional benefits", were labelled `member_service`: gpt-4o-mini 2, qwen3:8b 4, qwen3:14b 4 of 8. v2 limits `member_service` to an existing member's billing/claims/card question and says that asking about extra benefits is `plan_sales`. Equipment-campaign calls labelled `plan_sales` (3–4 of 9) were left alone: some of those calls really are plan pitches, so dev can't show them as errors.
- **"Recording notice" (`recording_disclosed`).** Outbound calls that start with the customer answering ("Hello? Hello…") and contain no recording notice got `null`: gpt-4o-mini 10, qwen3:14b 11 of 18 (qwen3:8b answered `false`). The schema's rule ("false only if the opening is in the transcript") was not enough to recognise "Hello?" as the opening.
- **"Outcome" (`outcome` / `agent_handoff`).** qwen3:8b used `issue_resolved` on 11 dev calls, 4 of them sales or equipment calls; qwen3:14b once gave `outcome = transfer` with `agent_handoff = false`. v2 ties `issue_resolved` to `member_service` and `transfer` to `agent_handoff = true`.

## v1 rewritten as a minimal baseline — 2026-11-01
Course lesson 4 defines the cycle as baseline v1 (the simplest prompt) → per-field error analysis → v2 with one change per error. The previous v1 already carried hand-written rules (null handling, speakers, ASR, handoffs, evidence quotes) that no measured error had motivated, so v1 is now only the task, the transcript in `<transcript>` tags as data (not instructions), and "follow the schema". The field definitions reach the model through the schema (OpenAI structured output; Ollama gets it appended to the system prompt). v2 is rebuilt from v1's dev-set errors. The old rule-based v1 and v2 texts are in git history; their results are in `results/archive/schema_v2_with_disclaimer/`.

# History: prompts before 2026-11-01
The entries below describe the earlier rule-based v1/v2, replaced on 2026-11-01. Their texts are in git history; their results are in `results/archive/schema_v2_with_disclaimer/`.

### v1 and v2 (revised for schema v3) — 2026-11-01
Schema v3 drops `compliance.disclaimer_before_benefits`, so the prompt text about it is removed from both versions. These are scope edits, not fixes, so the version numbers stay; the file hashes changed and every result records them. All combinations were re-run.
- v1 and v2: removed the `not_applicable` rule for the disclaimer and the "Benefits discussed" section (it existed only to time the disclaimer); the "Unknown, null and not_applicable" heading is now "Unknown and null".
- v2: removed the "Deciding the disclaimer" section. v2 is now v1 plus "Who started the call" and "Call type"; the v2 entry below describes the original three changes.

### v2 — 2026-10-31
Written from the v1 errors on the **26 dev calls only** (deterministic runs of all three models). No golden transcript or per-call golden error was opened; the aggregate v1 golden scores in `results/metrics.md` (e.g. gpt-4o-mini direction 0.10) were visible, so v2's choice of fields was not blind to them, but every change is backed by the dev-set numbers below. v2 = v1 plus three sections; nothing else changed, so v1 → v2 differences come from these.
- **"Who started the call" (`direction`).** gpt-4o-mini never answered `outbound` on the 18 outbound dev calls: outbound_plan → 5 `unknown`, 4 `inbound`; outbound_equipment → 4 `inbound`, 4 `unknown`, 1 `outbound`. The openings are clear ("the purpose of my call is…", "I'm calling about your benefits", "the one who called you a while ago"), so v2 lists these cues. It also covers the inbound_plan opening, a screener's warm transfer ("I have Ms. … on the line, she is interested in…"), which gpt-4o-mini marked `unknown` on 3 of 8 dev calls.
- **"Call type" (`call_type`).** Equipment campaigns also pitch "additional benefits at no cost" after checking Medicare Part A/B, and every model labelled 4 of 9 dev equipment calls `plan_sales`. gpt-4o-mini also used `other` on 3 plan-sales and 2 equipment calls ("your Medicare is getting upgraded" pitches). v2 decides the type by what is offered and says that an eligibility check alone is not plan sales.
- **"Deciding the disclaimer" (`disclaimer_before_benefits`).** qwen3:8b answered `not_applicable` on 25 of 26 dev calls, including plan-sales calls where benefits were pitched. v2 gives an explicit order: first decide whether plan benefits were described; if yes, the answer is `yes` or `no`, never `not_applicable`. The screener → licensed agent rule from `LABELING.md` is now in the prompt.

### v1 (revised for schema v2) — 2026-10-24
Scope narrowed to Medicare-only calls (schema v2: `call_type` replaces `domain`; `customer_intent` and `next_action` dropped). Changes are scope edits, not fixes from dev-set errors, so this stays v1; the file hash changed and every result records it.
- Role: "QA and compliance analyst for Medicare sales and service calls".
- `recording_disclosed = false` only when the call's opening is in the transcript; otherwise `null` (a notice may precede the recording).
- `disclaimer_before_benefits = not_applicable` when no Medicare plan benefits are discussed (equipment offers, service questions).
- "Benefits discussed" names Medicare Advantage, Part D and supplement plans.

### v1 — 2026-10-24
Baseline. Covers what the schema cannot: when to use null / `unknown` / `not_applicable`, inferring agent vs customer without speaker labels, ASR errors and PII placeholders, multiple agents (`agent_handoff` vs `outcome = transfer`), what counts as "benefits discussed" for Medicare, and verbatim evidence quotes.

### Client change (no prompt version bump): schema shown to Ollama models
Ollama's `format` only constrains decoding; unlike OpenAI structured outputs it does not show the
schema to the model. `OllamaClient` now appends the JSON schema (with field descriptions) to the system
prompt, so both backends see the same field definitions. qwen3:8b runs before this change are in
`results/archive/qwen_no_schema_in_prompt/` (call_type 0.17, always `not_applicable`, looping on long calls).
