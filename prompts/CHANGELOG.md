# Prompt changelog

## v2 — 2026-10-31
Written from the v1 errors on the **26 dev calls only** (deterministic runs of all three models; golden calls not opened). v2 = v1 plus three sections; nothing else changed, so v1 → v2 differences come from these.
- **"Who started the call" (`direction`).** gpt-4o-mini never answered `outbound` on the 18 outbound dev calls: outbound_plan → 5 `unknown`, 4 `inbound`; outbound_equipment → 4 `inbound`, 4 `unknown`, 1 `outbound`. The openings are clear ("the purpose of my call is…", "I'm calling about your benefits", "the one who called you a while ago"), so v2 lists these cues. It also covers the inbound_plan opening, a screener's warm transfer ("I have Ms. … on the line, she is interested in…"), which gpt-4o-mini marked `unknown` on 3 of 8 dev calls.
- **"Call type" (`call_type`).** Equipment campaigns also pitch "additional benefits at no cost" after checking Medicare Part A/B, and every model labelled 4 of 9 dev equipment calls `plan_sales`. gpt-4o-mini also used `other` on 3 plan-sales and 2 equipment calls ("your Medicare is getting upgraded" pitches). v2 decides the type by what is offered and says that an eligibility check alone is not plan sales.
- **"Deciding the disclaimer" (`disclaimer_before_benefits`).** qwen3:8b answered `not_applicable` on 25 of 26 dev calls, including plan-sales calls where benefits were pitched. v2 gives an explicit order: first decide whether plan benefits were described; if yes, the answer is `yes` or `no`, never `not_applicable`. The screener → licensed agent rule from `LABELING.md` is now in the prompt.

## v1 (revised for schema v2) — 2026-10-24
Scope narrowed to Medicare-only calls (schema v2: `call_type` replaces `domain`; `customer_intent` and `next_action` dropped). Changes are scope edits, not fixes from dev-set errors, so this stays v1; the file hash changed and every result records it.
- Role: "QA and compliance analyst for Medicare sales and service calls".
- `recording_disclosed = false` only when the call's opening is in the transcript; otherwise `null` (a notice may precede the recording).
- `disclaimer_before_benefits = not_applicable` when no Medicare plan benefits are discussed (equipment offers, service questions).
- "Benefits discussed" names Medicare Advantage, Part D and supplement plans.

## v1 — 2026-10-24
Baseline. Covers what the schema cannot: when to use null / `unknown` / `not_applicable`, inferring agent vs customer without speaker labels, ASR errors and PII placeholders, multiple agents (`agent_handoff` vs `outcome = transfer`), what counts as "benefits discussed" for Medicare, and verbatim evidence quotes.

## Client change (no prompt version bump): schema shown to Ollama models
Ollama's `format` only constrains decoding; unlike OpenAI structured outputs it does not show the
schema to the model. `OllamaClient` now appends the JSON schema (with field descriptions) to the system
prompt, so both backends see the same field definitions. qwen3:8b runs before this change are in
`results/archive/qwen_no_schema_in_prompt/` (call_type 0.17, always `not_applicable`, looping on long calls).
