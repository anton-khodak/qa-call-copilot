# Prompt changelog

## v2 — 2026-11-01
v1 plus four sections, one per error class seen with v1 on the **26 dev calls** (deterministic runs of all three models). No golden transcript, golden error or golden per-field score was used.
- **"Who started the call" (`direction`).** gpt-4o-mini answered `inbound` on 16 of the 18 outbound-campaign dev calls (qwen3:8b 4, qwen3:14b 5). The openings are unambiguous ("the purpose of my call is…", "I'm calling you from…", "the one who called you a while ago", or the customer answering "Hello?"), so v2 lists these cues.
- **"Call type" (`call_type`).** Inbound plan-sales calls, where a screener passes on a customer "interested in Medicare Part C additional benefits", were labelled `member_service`: gpt-4o-mini 2, qwen3:8b 4, qwen3:14b 4 of 8. v2 limits `member_service` to an existing member's billing/claims/card question and says that asking about extra benefits is `plan_sales`. Equipment-campaign calls labelled `plan_sales` (3–4 of 9) were left alone: some of those calls really are plan pitches, so dev can't show them as errors.
- **"Recording notice" (`recording_disclosed`).** Outbound calls that start with the customer answering ("Hello? Hello…") and contain no recording notice got `null`: gpt-4o-mini 10, qwen3:14b 11 of 18 (qwen3:8b answered `false`). The schema's rule ("false only if the opening is in the transcript") was not enough to recognise "Hello?" as the opening.
- **"Outcome" (`outcome` / `agent_handoff`).** qwen3:8b used `issue_resolved` on 11 dev calls, 4 of them sales or equipment calls; qwen3:14b once gave `outcome = transfer` with `agent_handoff = false`. v2 ties `issue_resolved` to `member_service` and `transfer` to `agent_handoff = true`.

## v1 — 2026-11-01
Minimal baseline, per the course lesson 4 cycle (simplest prompt → per-field error analysis → v2 with one change per error): the task, the transcript in `<transcript>` tags as data (not instructions), and "follow the schema". The field definitions reach the model through the schema (OpenAI structured output; Ollama gets it appended to the system prompt).
