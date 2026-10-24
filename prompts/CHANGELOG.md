# Prompt changelog

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
