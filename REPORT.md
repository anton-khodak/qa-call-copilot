# HW1 report: structured extraction from Medicare call transcripts

Which model, prompt and sampling setting should turn raw Medicare sales calls into the QA record in `src/schema.py`? This report gives the measured comparison, the typical errors, and the production choice.

**Summary**
- **Production choice: `qwen3:8b` + prompt v2 + `deterministic`.** Ties for the best golden average among the three candidates (0.72), the only candidate with `recording_disclosed` at 1.00, 6 s per call, $0, and no data leaves our machines.
- **Prompt v1 → v2** (one section per dev-set error class) raises every model's six-field average: gpt-4o-mini 0.62 → 0.70, qwen3:14b 0.63 → 0.69, qwen3:8b 0.54 → 0.72.
- **Sampling** barely matters for extraction: `low` (T 0.3) and `deterministic` (T 0) differ by at most one call per field, in both directions; `deterministic` wins on reproducibility.
- **Validity:** 784 of 784 outputs were schema-valid on the first try; the repair path is covered by unit tests only.
- **Frontier reference, Opus 5.5:** 0.82 (v1) and 0.87 (v2), 1.00 on `call_type`, `agent_handoff` and `recording_disclosed`. Part of that lead is circular (the golden labels were adjudicated against Opus's own blind labels); against the original hand labels it is 0.73 vs 0.67–0.68 for the best small setups. At $23.5 per 1,000 calls and with the least repeatable output, it is a reference and a reviewer's aid, not the production model.
- With 10 golden calls, 0.10 is one call; differences under 0.10 are within noise.

## Setup

- **Data:** 36 Medicare calls from CallCenterEN (AIxBlock), 12 per campaign (inbound plan sales, outbound plan sales, outbound medical equipment). The ASR text goes in raw, with no speaker labels and PII already masked. 10 calls are the **golden set**: hand-labelled per `data/golden/LABELING.md` and adjudicated against two blind model labellings. The other 26 are the **dev set**, used for prompt work. Details in `data/README.md`.
- **Schema:** `call_type`, `direction`, `outcome` (inferred enums); `objections` (nested list of type + handled); `compliance.recording_disclosed` (nested object: value + verbatim evidence); `agent_handoff`. Every field is defined once, in `Field(description=...)`, and passed through structured output.
- **Models:**
  - `openai/gpt-4o-mini` via OpenRouter: JSON-schema structured output, $0.15 / $0.60 per 1M tokens.
  - `qwen3:8b` and `qwen3:14b` locally on Ollama: thinking off, 16k context, JSON-schema `format`, with the schema also appended to the system prompt.
  - Local runs are on a 24 GB Apple M5 laptop. Their API cost is $0; the hardware isn't priced.
  - **Frontier reference:** `claude-opus-5-5` through the local Claude Code CLI (`claude -p --json-schema`, `make frontier`, `src/clients/claude_code.py`): the prompt is the whole system prompt, no tools, settings or MCP servers, run from an empty directory. The CLI has no sampling flags, so Opus runs with its defaults (adaptive thinking on) as a third sampling setting, `cli_default`. Cost is the CLI's reported list price, which includes prompt caching and thinking tokens. It is a reference for how far the small models are from the best available model, not a production candidate (see below).
- **Prompts** (`prompts/`, history in `prompts/CHANGELOG.md`). Following the lesson 4 cycle:
  - **v1 is the minimal baseline:** the task, the transcript in `<transcript>` tags as data, and "follow the schema" (36 words).
  - **v2 = v1 plus four short sections**, one per error class that v1 made on the **dev set** (field by field, with counts in the changelog): who started the call, call type, recording notice, outcome.
- **Sampling** (`config/sampling.yaml`): `deterministic` (temperature 0, top_p 1, seed 42) and `low` (temperature 0.3, top_p 0.9, seed 42); `cli_default` (Opus only: no temperature, top_p or seed can be set).
- **Runs:** 3 models × 2 prompts × 2 samplings = 12 combinations, plus Opus × 2 prompts. Each runs on all 36 calls, with the 10 golden calls run three times: 56 records per combination, 784 in total. Spend: $0.09 on OpenRouter; Opus $2.67 at list price, billed to the Claude Code login.
- **Validation and logging:** each output is validated against the Pydantic schema. An invalid output gets exactly one repair call (previous output + validation error), then is marked `failed` (`src/extract.py`). Every record logs model, prompt version and hash, schema version, sampling name, temperature, top_p, seed, status, latency, tokens and cost.
- **Metrics** (`src/eval.py`):
  - accuracy per field on the golden set: median of the 3 runs, and a failed record counts as wrong;
  - objections: precision / recall / F1 on types;
  - `call type acc (all)`: `call_type` on all 36 calls, compared with the campaign the call came from;
  - latency p50 / p95 per call;
  - cost per 1,000 calls, from actual token usage.

## Comparison

Validity, latency, cost and summary accuracy (`results/metrics.md`). "extracted acc" averages `agent_handoff`, `recording_disclosed` and objections F1; "inferred acc" averages `call_type`, `direction` and `outcome`.

| model | prompt | sampling | valid 1st try % | repaired % | failed % | p50 s | p95 s | $ / 1k calls | call type acc (all) | extracted acc | inferred acc | objections F1 | golden runs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-opus-5-5 | v1 | cli_default | 100 | 0 | 0 | 5.6 | 10.6 | 24.088 | 0.75 | 0.91 | 0.73 | 0.73 | 3 |
| claude-opus-5-5 | v2 | cli_default | 100 | 0 | 0 | 5.8 | 10.0 | 23.535 | 0.78 | 0.91 | 0.83 | 0.73 | 3 |
| openai/gpt-4o-mini | v1 | deterministic | 100 | 0 | 0 | 1.3 | 1.9 | 0.393 | 0.64 | 0.70 | 0.53 | 0.50 | 3 |
| openai/gpt-4o-mini | v1 | low | 100 | 0 | 0 | 1.3 | 1.8 | 0.392 | 0.58 | 0.70 | 0.53 | 0.50 | 3 |
| openai/gpt-4o-mini | v2 | deterministic | 100 | 0 | 0 | 1.3 | 2.3 | 0.446 | 0.69 | 0.72 | 0.67 | 0.57 | 3 |
| openai/gpt-4o-mini | v2 | low | 100 | 0 | 0 | 1.3 | 2.0 | 0.444 | 0.69 | 0.72 | 0.67 | 0.57 | 3 |
| qwen3:14b | v1 | deterministic | 100 | 0 | 0 | 12.9 | 35.7 | 0.000 | 0.61 | 0.60 | 0.67 | 0.40 | 3 |
| qwen3:14b | v1 | low | 100 | 0 | 0 | 13.3 | 25.6 | 0.000 | 0.61 | 0.60 | 0.67 | 0.40 | 3 |
| qwen3:14b | v2 | deterministic | 100 | 0 | 0 | 13.1 | 44.2 | 0.000 | 0.72 | 0.61 | 0.77 | 0.44 | 3 |
| qwen3:14b | v2 | low | 100 | 0 | 0 | 12.0 | 21.7 | 0.000 | 0.72 | 0.67 | 0.77 | 0.50 | 3 |
| qwen3:8b | v1 | deterministic | 100 | 0 | 0 | 6.1 | 13.3 | 0.000 | 0.53 | 0.61 | 0.47 | 0.43 | 3 |
| qwen3:8b | v1 | low | 100 | 0 | 0 | 6.1 | 9.0 | 0.000 | 0.53 | 0.61 | 0.47 | 0.43 | 3 |
| qwen3:8b | v2 | deterministic | 100 | 0 | 0 | 6.2 | 16.8 | 0.000 | 0.64 | 0.77 | 0.67 | 0.60 | 3 |
| qwen3:8b | v2 | low | 100 | 0 | 0 | 6.9 | 11.3 | 0.000 | 0.64 | 0.69 | 0.67 | 0.36 | 3 |

Golden-set accuracy per field (median of 3 runs):

| model | prompt | sampling | call_type | direction | outcome | agent_handoff | recording_disclosed | obj P | obj R | obj F1 | handled |
|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-opus-5-5 | v1 | cli_default | 1.00 | 0.60 | 0.60 | 1.00 | 1.00 | 0.67 | 0.80 | 0.73 | 1.00 |
| claude-opus-5-5 | v2 | cli_default | 1.00 | 0.80 | 0.70 | 1.00 | 1.00 | 0.67 | 0.80 | 0.73 | 1.00 |
| openai/gpt-4o-mini | v1 | deterministic | 0.70 | 0.30 | 0.60 | 1.00 | 0.60 | 0.67 | 0.40 | 0.50 | 1.00 |
| openai/gpt-4o-mini | v1 | low | 0.70 | 0.30 | 0.60 | 1.00 | 0.60 | 0.67 | 0.40 | 0.50 | 1.00 |
| openai/gpt-4o-mini | v2 | deterministic | 0.90 | 0.50 | 0.60 | 0.80 | 0.80 | 1.00 | 0.40 | 0.57 | 0.00 |
| openai/gpt-4o-mini | v2 | low | 0.90 | 0.50 | 0.60 | 0.80 | 0.80 | 1.00 | 0.40 | 0.57 | 0.50 |
| qwen3:14b | v1 | deterministic | 0.70 | 0.60 | 0.70 | 0.80 | 0.60 | 0.40 | 0.40 | 0.40 | 1.00 |
| qwen3:14b | v1 | low | 0.70 | 0.60 | 0.70 | 0.80 | 0.60 | 0.40 | 0.40 | 0.40 | 1.00 |
| qwen3:14b | v2 | deterministic | 1.00 | 0.60 | 0.70 | 0.80 | 0.60 | 0.50 | 0.40 | 0.44 | 1.00 |
| qwen3:14b | v2 | low | 1.00 | 0.60 | 0.70 | 0.80 | 0.70 | 0.67 | 0.40 | 0.50 | 1.00 |
| qwen3:8b | v1 | deterministic | 0.60 | 0.40 | 0.40 | 0.70 | 0.70 | 0.33 | 0.60 | 0.43 | 1.00 |
| qwen3:8b | v1 | low | 0.60 | 0.40 | 0.40 | 0.70 | 0.70 | 0.33 | 0.60 | 0.43 | 1.00 |
| qwen3:8b | v2 | deterministic | 0.90 | 0.60 | 0.50 | 0.70 | 1.00 | 0.60 | 0.60 | 0.60 | 1.00 |
| qwen3:8b | v2 | low | 0.90 | 0.60 | 0.50 | 0.70 | 1.00 | 0.33 | 0.40 | 0.36 | 1.00 |

For scale, a constant answer would score: `call_type` = `plan_sales` 0.90 (9 of 10 golden calls are plan sales), `direction` = `outbound` 0.60, `outcome` = `transfer` 0.40, `agent_handoff` = true 0.70, `recording_disclosed` = true 0.60. Only one golden call contains objections, so the objection columns rest on that single call.

**What the numbers say**

- **Validity is not a differentiator.** All 784 records were schema-valid on the first try, so the repair path never fired in real runs. Constrained decoding (OpenAI strict JSON schema, Ollama `format`, the Claude CLI's `--json-schema`) already guarantees the shape, and no run hit the 1,024-token output cap or the 16k context. Unit tests in `tests/test_extract.py` cover the repair path: invalid→valid, invalid twice, empty output, a timeout on the repair call, and token accounting.
- **v1 → v2 helps every model.** The average over the six scored fields rises from 0.62 to 0.70 (gpt-4o-mini), 0.63 to 0.69–0.72 (qwen3:14b) and 0.54 to 0.68–0.72 (qwen3:8b).
  - The `call_type` section fixes the `member_service` confusion: 0.60–0.70 → 0.90–1.00.
  - The recording section takes qwen3:8b from 0.70 to 1.00 and gpt-4o-mini from 0.60 to 0.80.
  - gpt-4o-mini's `direction` goes from 0.30 to 0.50.
  - The cost of the extra rules: gpt-4o-mini's input grows from $0.39 to $0.45 per 1,000 calls.
  - **One regression:** gpt-4o-mini's `agent_handoff` drops from 1.00 to 0.80 (error 5).
- **Sampling.** `deterministic` and `low` give the same golden accuracy for gpt-4o-mini (apart from `handled` on the single objection call), and differ by at most one call per field for qwen3:14b. qwen3:8b with `low` loses the one objection call (F1 0.60 → 0.36). Temperature 0.3 buys nothing reliable for extraction (qwen3:14b v2 gains one call on two fields, qwen3:8b loses one), so `deterministic` is the choice: reproducible, and it matches the course guidance (T≈0).
- **Model size.** qwen3:14b is the only small model with `call_type` = 1.00 and has the best `direction` (tied with qwen3:8b v2 at 0.60, which is only the constant-`outbound` level). It takes about 2× longer than qwen3:8b (p50 13 s vs 6 s). With v2, qwen3:8b catches up on the averages and beats it on `recording_disclosed` (1.00 vs 0.60–0.70).
- **Latency and cost.** gpt-4o-mini answers in 1.3 s (p95 ≤ 2.3 s) for $0.45 per 1,000 calls with v2. The local models cost nothing per call but take 6–13 s (p95 up to 44 s) on the laptop.

With 10 golden calls, 0.10 is one call. The three v2 deterministic setups are within one call of each other on the average (0.69–0.72). The ranking below therefore also weighs which fields each model gets wrong.

## Frontier reference: Opus 5.5

**On the golden set, Opus is clearly ahead:** the six-field average is 0.82 with v1 and 0.87 with v2, against 0.70–0.72 for the best small setups. It gets `call_type`, `agent_handoff` and `recording_disclosed` right on every golden call with both prompts, and v2 still helps it (`direction` 0.60 → 0.80, `outcome` 0.60 → 0.70). Its minimal-v1 score is already above every small model with v2: most of what v2 spells out, Opus infers from the schema descriptions alone.

**But part of that lead is circular.** The golden labels were adjudicated against two blind model labellings, one of them by Opus 5.5 (`data/golden/opus.jsonl`). In 12 places my first hand label was changed to Opus's answer after review (`data/golden/review.json`), and the blind Opus labels now match the golden set on 48 of 50 scalar fields. Scored against my original hand labels instead, the averages are:

| setup | adjudicated golden | original hand labels |
|---|---|---|
| Opus 5.5, v2 | 0.87 | 0.73 |
| Opus 5.5, v1 | 0.82 | 0.73 |
| gpt-4o-mini, v2, deterministic | 0.70 | 0.68 |
| qwen3:8b, v2, deterministic | 0.72 | 0.67 |
| qwen3:14b, v2, deterministic | 0.69 | 0.62 |

Opus stays first, but its lead over the best small setup shrinks from about 1.5 golden calls to about half a call; the small models move by 0.02–0.07. The honest reading: Opus is the best of the four, by an amount this golden set can't pin down. The fix is labels made without any model in the loop for the calls used to compare models (next steps).

**Where Opus still fails** (v2, run 0) is where the small models fail too, which points at genuinely ambiguous calls rather than weak models:
- `direction` on the two warm transfers (2021-08-18, 2021-08-19: golden `unknown`, Opus `outbound`) and on 2021-08-25 (golden `outbound`, Opus `inbound`).
- `outcome` on calls without a clear ending: `callback` vs `other`, `not_interested` vs `other`, and DMEMED_rmbpo18 (`callback` vs `sale`, the same call as error 5).
- objections on calls where the golden set has none (a `price` or `already_covered` remark that the golden labels didn't count as an objection).

**Reproducibility.** Without temperature control Opus is the least stable setup: across its three golden runs, 7 of 60 call-fields change with v1 and 3 of 60 with v2, against 0–3 for every other setup. The median over three runs hides this in the table.

**Cost and latency.** $23.5 per 1,000 calls at list price (about 50× gpt-4o-mini), p50 5.8 s, p95 10 s. The CLI cost includes 1-hour cache writes and its structured-output tool; a direct API call with the same prompt would be somewhat cheaper, but the same order of magnitude.

## Error analysis

Every disagreement with the golden set is in `results/golden_errors.csv` (`make errors`). Counts are from the deterministic runs, run 0. Five typical errors:

**1. `direction` without speaker labels: fixed for outbound calls, broken for inbound ones.**
- **v1 error:** gpt-4o-mini answered `inbound` on outbound calls such as 4104666105 ("the reason I'm calling you today is because…") and 5169932905 ("the reason of my call is to let you know that your Medicare is getting upgraded"). With no speakers, the model seems to judge by who asks for what. v2's opening cues fixed both.
- **New v2 error:** I wrote one cue too broadly, "the customer answering and the agent introducing themselves is outbound". All three models now call 2021-08-27-19-48-40 `outbound`, though it opens "This call may be recorded. Good afternoon, this is Ms. [PERSON_NAME] on a recorded line. How can I help you?", which is an inbound greeting. They do the same with the warm transfers 2021-08-18 and 2021-08-19 (golden `unknown`), where a licensed agent introduces themselves after "I have Ms. [PERSON_NAME] on the line".
- **Opus 5.5 has the same trouble:** it calls the warm transfer 2021-08-19 `outbound` with both prompts (and 2021-08-18 with v1), so these calls are hard from the text alone, not only for small models.
- **Fix for v3:** "How can I help you?" means inbound, and a screener's warm transfer alone is `unknown`.

**2. `recording_disclosed`: `null` instead of `false`, partly fixed.**
- **The case:** outbound calls such as 9312963581 and 4104666105 start with the customer's "Hello?" and never mention recording, so the golden label is `false`. gpt-4o-mini and qwen3:14b answered `null` with v1, because the schema allows `null` when the transcript may start mid-call.
- **After v2:** the "Recording notice" section fixed DMEMED_rmbpo06 and DMEMED_rmbpo18 for gpt-4o-mini, and every call for qwen3:8b.
- **Still wrong:** gpt-4o-mini keeps `null` on 9312963581 and 4104666105. qwen3:14b ignores the rule on all four calls (deterministic accuracy stays at 0.60).
- **Likely cause:** the schema description that is passed with every call also says `null` "if the transcript … is too short or broken to tell". 9312963581 and 4104666105 are short (394 and 593 words) and broken, so the two instructions conflict, and the models follow the schema.
- **Opus 5.5** answers `false` on all four calls with both prompts (1.00): it resolves the conflict the way the golden labels do.
- **Fix:** change the field description, not the prompt.

**3. A recording "notice" that isn't one (qwen3:8b, v1).**
- **The case:** with v1, qwen3:8b answered `recording_disclosed = true` on three outbound calls with no notice. Its evidence quotes are real transcript text, but none of them is a notice:
  - "Hello? Hello? Hi, this is [PERSON_NAME] here from [ORGANIZATION]…" (4104666105)
  - "This call is regarding for your benefits at no cost to you." (DMEMED_rmbpo18)
- **Why the code check missed it:** the check confirms the quote exists in the transcript, which it does; it can't tell whether the quote says what the field claims.
- **After v2:** fixed (1.00).
- **Lesson:** a verbatim-quote check catches invented quotes, not misread ones.

**4. `call_type`: a Medicare member asking about benefits labelled as member service (fixed); equipment vs plans (open).**
- **The fixed case:** in 2021-08-18-14-54-00 the screener says the customer "is interested in learning more about Medicare Part 3 and additional benefits". With v1, every model answered `member_service`, since an existing Medicare member is asking about benefits. v2 limits `member_service` to an existing member's billing, claims or card questions, and `call_type` rises to 0.90–1.00.
- **The open case:** DMEMED_rmbpo18_20211221 is an equipment offer pitched as "your benefits at no cost to you … some new benefits recently became available that you may qualify for". The product itself is masked (`[MEDICAL_PROCESS]`). gpt-4o-mini (v1 and v2) and qwen3:8b with v2 call it `plan_sales`, because equipment and plan campaigns share the same script. Opus 5.5 gets it right (`call_type` 1.00 with both prompts), so the text does carry the signal.
- **A caveat on `call type acc (all)`:** two of the three golden calls from the equipment campaign are labelled `plan_sales`, so this metric, which scores against the campaign, is only a rough proxy.

**5. One outcome error spreads to `agent_handoff` (gpt-4o-mini's v2 regression).**
- **The call:** DMEMED_rmbpo18_20211221 ends with the agent putting in the order herself: "do you have any questions for me before I put in a request for you? … don't forget to pick up the next phone call". The golden label is `outcome = sale`, `agent_handoff = false`.
- **v1:** gpt-4o-mini said `callback`, with `agent_handoff = false`.
- **v2:** it says `transfer`, and v2's rule "`transfer` always comes with `agent_handoff = true`" turns the wrong outcome into a second wrong field. Together with 2021-08-19, where the handoff happens in the first seconds ("I'm connecting you call") and is missed, this is gpt-4o-mini's `agent_handoff` drop from 1.00 to 0.80.
- **Opus 5.5** also answers `callback` on this call, with both prompts, but keeps `agent_handoff = false` (1.00): the outcome is genuinely ambiguous from the text; the handoff is not.
- **The broader point:** coupling rules between fields make the output consistent, but an error in one field now carries over to the other. A code check that reports the inconsistency (instead of the prompt forcing it) would keep the two fields independent.

## Production choice

**qwen3:8b with prompt v2 and `deterministic` sampling, used for batch QA of the previous day's calls, with flagged calls reviewed by a human.**
- **Accuracy:** it ties for the best average of the three candidates on the golden set (0.72).
- **The compliance field:** it is the only small-model setup with `recording_disclosed` at 1.00 (Opus also has 1.00), against 0.80 for gpt-4o-mini and 0.60–0.70 for qwen3:14b. That field is the remaining compliance check, and the one a wrong answer hurts most.
- **Cost and speed:** it runs at 6 s per call, about 14,000 calls a day sequentially on one laptop, at $0 per call.
- **Data protection:** production transcripts (unmasked health and personal data of Medicare members) never leave our machines.
- **Its weak spots:** `agent_handoff` (0.70) and `outcome` (0.50). Reports that depend on those need review.

**Why not Opus 5.5**, the most accurate setup:
- **Cost:** about $23.5 per 1,000 calls, so a million calls a month is about $23,500, against $0 for qwen3:8b; the measured gain is between half a call and 1.5 calls out of 10, depending on whose labels you trust.
- **Data protection:** the same objection as gpt-4o-mini, raw health data leaves our machines.
- **Reproducibility:** no temperature control through the CLI, and the most run-to-run variation; a QA verdict that changes on re-run is hard to defend to an agent.
- **Where it does belong:** as a second opinion on the calls the code checks flag, and as a labelling assistant for the larger golden set, with the human label recorded first so the circularity above stays measurable.

**I would change the choice if:**
- **QA must answer in seconds** (live agent assist): switch to gpt-4o-mini (1.3 s, $0.45 per 1,000 calls; a million calls a month is about $450 in API fees).
- **Call routing matters more than compliance:** qwen3:14b is the only small model with `call_type` at 1.00, at 2× the latency.
- **A provider agreement covering health data** (e.g. a BAA) makes sending raw transcripts acceptable.
- **A larger golden set ranks the models differently.** With 10 calls, the three v2 setups are within one call of each other on average.

## Next steps

- Prompt v3: narrow the outbound cue ("How can I help you?" = inbound; a warm transfer alone = `unknown`).
- Remove the "too short or broken" clause from the `recording_disclosed` description; resolve the conflict with the prompt in the schema.
- Replace the transfer⇒handoff prompt rule with a code check that flags the inconsistency.
- Grow the golden set to 30+ calls, with more objections and more equipment and member-service calls, and keep a hand-only label for each call (no model in the adjudication loop) so the comparison with Opus is not circular.
