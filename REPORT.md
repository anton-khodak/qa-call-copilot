# HW1 report: structured extraction from Medicare call transcripts

Which model, prompt and sampling setting should turn raw Medicare sales calls into the QA record in `src/schema.py`? This report gives the measured comparison, the typical errors, and the production choice.

## Setup

- **Data:** 36 Medicare calls from CallCenterEN (AIxBlock), 12 per campaign (inbound plan sales, outbound plan sales, outbound medical equipment); ASR text fed raw, no speaker labels, PII already masked. 10 calls are the **golden set** (hand-labelled per `data/golden/LABELING.md`, adjudicated against two blind model labellings); 26 are the **dev set**, used for prompt work. Details in `data/README.md`.
- **Models:** `openai/gpt-4o-mini` via OpenRouter (JSON-schema structured output, $0.15 / $0.60 per 1M tokens) and two local models on Ollama, `qwen3:8b` and `qwen3:14b` (thinking off, 16k context, JSON-schema `format`, schema also shown in the system prompt). Local runs on a 24 GB Apple M5 laptop; their API cost is $0, hardware not priced.
- **Prompts:** `prompts/extract_v1.md` (baseline) and `prompts/extract_v2.md` (v1 + three sections written from dev-set errors; see `prompts/CHANGELOG.md`).
- **Sampling** (`config/sampling.yaml`): `deterministic` (temperature 0, top_p 1, seed 42) and `low` (temperature 0.3, top_p 0.9, seed 42).
- **Runs:** every combination (3 models × 2 prompts × 2 samplings = 12) on all 36 calls, the 10 golden calls three times each: 56 records per combination, 672 in total. Total API spend for all runs in `results/runs/`: $0.13.
- **Validation:** each output is validated against the Pydantic schema; an invalid one gets exactly one repair call (previous output + validation error), then `failed` (`src/extract.py`). Each record logs model, prompt version and hash, sampling name, temperature, top_p and seed.
- **Metrics** (`src/eval.py`): accuracy per field on the golden set, median over the 3 runs, a failed record counts as wrong; objections as precision / recall / F1 on types; `call type acc (all)` compares `call_type` on all 36 calls with the campaign the call came from; latency p50 / p95 per call (including a repair call if any); cost per 1,000 calls from real token usage.

## Comparison

Validity, latency, cost and summary accuracy (`results/metrics.md`):

| model | prompt | sampling | valid 1st try % | repaired % | failed % | p50 s | p95 s | $ / 1k calls | call type acc (all) | extracted acc | inferred acc | objections F1 | golden runs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| openai/gpt-4o-mini | v1 | deterministic | 100 | 0 | 0 | 1.7 | 3.2 | 0.528 | 0.64 | 0.62 | 0.50 | 0.50 | 3 |
| openai/gpt-4o-mini | v1 | low | 100 | 0 | 0 | 1.6 | 2.7 | 0.528 | 0.61 | 0.65 | 0.53 | 0.50 | 3 |
| openai/gpt-4o-mini | v2 | deterministic | 100 | 0 | 0 | 1.7 | 2.5 | 0.604 | 0.58 | 0.59 | 0.63 | 0.57 | 3 |
| openai/gpt-4o-mini | v2 | low | 100 | 0 | 0 | 1.7 | 3.6 | 0.605 | 0.56 | 0.59 | 0.63 | 0.57 | 3 |
| qwen3:14b | v1 | deterministic | 100 | 0 | 0 | 15.6 | 33.7 | 0.000 | 0.64 | 0.59 | 0.63 | 0.44 | 3 |
| qwen3:14b | v1 | low | 100 | 0 | 0 | 22.5 | 46.2 | 0.000 | 0.64 | 0.56 | 0.63 | 0.44 | 3 |
| qwen3:14b | v2 | deterministic | 100 | 0 | 0 | 16.0 | 43.7 | 0.000 | 0.64 | 0.64 | 0.60 | 0.44 | 3 |
| qwen3:14b | v2 | low | 100 | 0 | 0 | 16.3 | 33.0 | 0.000 | 0.64 | 0.64 | 0.60 | 0.44 | 3 |
| qwen3:8b | v1 | deterministic | 100 | 0 | 0 | 7.9 | 16.7 | 0.000 | 0.47 | 0.62 | 0.37 | 0.36 | 3 |
| qwen3:8b | v1 | low | 100 | 0 | 0 | 8.7 | 17.0 | 0.000 | 0.47 | 0.62 | 0.37 | 0.36 | 3 |
| qwen3:8b | v2 | deterministic | 100 | 0 | 0 | 7.6 | 15.6 | 0.000 | 0.58 | 0.60 | 0.63 | 0.31 | 3 |
| qwen3:8b | v2 | low | 100 | 0 | 0 | 8.5 | 16.4 | 0.000 | 0.58 | 0.60 | 0.63 | 0.29 | 3 |

Golden-set accuracy per field (median of 3 runs):

| model | prompt | sampling | call_type | direction | outcome | agent_handoff | recording_disclosed | disclaimer_before_benefits | obj P | obj R | obj F1 | handled |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| openai/gpt-4o-mini | v1 | deterministic | 0.80 | 0.10 | 0.60 | 0.90 | 0.60 | 0.50 | 0.67 | 0.40 | 0.50 | 0.00 |
| openai/gpt-4o-mini | v1 | low | 0.80 | 0.20 | 0.60 | 0.90 | 0.60 | 0.60 | 0.67 | 0.40 | 0.50 | 0.00 |
| openai/gpt-4o-mini | v2 | deterministic | 0.70 | 0.60 | 0.60 | 0.80 | 0.60 | 0.40 | 1.00 | 0.40 | 0.57 | 0.00 |
| openai/gpt-4o-mini | v2 | low | 0.70 | 0.60 | 0.60 | 0.90 | 0.60 | 0.30 | 1.00 | 0.40 | 0.57 | 0.00 |
| qwen3:14b | v1 | deterministic | 0.60 | 0.60 | 0.70 | 0.80 | 0.60 | 0.50 | 0.50 | 0.40 | 0.44 | 1.00 |
| qwen3:14b | v1 | low | 0.60 | 0.60 | 0.70 | 0.70 | 0.60 | 0.50 | 0.50 | 0.40 | 0.44 | 1.00 |
| qwen3:14b | v2 | deterministic | 0.60 | 0.60 | 0.60 | 0.80 | 0.60 | 0.70 | 0.50 | 0.40 | 0.44 | 1.00 |
| qwen3:14b | v2 | low | 0.60 | 0.60 | 0.60 | 0.80 | 0.60 | 0.70 | 0.50 | 0.40 | 0.44 | 1.00 |
| qwen3:8b | v1 | deterministic | 0.50 | 0.20 | 0.40 | 0.70 | 1.00 | 0.40 | 0.33 | 0.40 | 0.36 | 1.00 |
| qwen3:8b | v1 | low | 0.50 | 0.20 | 0.40 | 0.70 | 1.00 | 0.40 | 0.33 | 0.40 | 0.36 | 1.00 |
| qwen3:8b | v2 | deterministic | 0.80 | 0.60 | 0.50 | 0.70 | 0.90 | 0.50 | 0.25 | 0.40 | 0.31 | 0.50 |
| qwen3:8b | v2 | low | 0.80 | 0.60 | 0.50 | 0.70 | 0.90 | 0.50 | 0.22 | 0.40 | 0.29 | 0.50 |

**What the numbers say**

- **Validity is not a differentiator.** All 672 records were schema-valid on the first try; the repair path never fired in real runs. Constrained decoding (OpenAI strict JSON schema, Ollama `format`) already guarantees the shape, and no run hit the 1,024-token output cap or the 16k context on Ollama. The repair path is covered by unit tests (`tests/test_extract.py`: invalid→valid, invalid twice, empty output, repair-call timeout, token accounting).
- **Prompt v1 → v2.** `direction` improved the most: gpt-4o-mini 0.10 → 0.60 and qwen3:8b 0.20 → 0.60. qwen3:8b also improved on `call_type` (0.50 → 0.80). qwen3:14b's disclaimer accuracy rose from 0.50 to 0.70. One change backfired: v2 made gpt-4o-mini's disclaimer worse (0.50 → 0.40 deterministic, 0.60 → 0.30 low). Error 2 below explains why. Averaged over the seven scored fields, all three models reach about 0.61–0.62 with v2, against 0.51–0.61 with v1.
- **Sampling.** `deterministic` and `low` differ by at most one golden call per field. The local models are nearly identical across the two. Temperature 0.3 buys nothing here, so `deterministic` is the choice (reproducible runs).
- **Model size.** qwen3:14b is about 2× slower than qwen3:8b (p50 16 s vs 8 s). It has the best disclaimer accuracy (0.70 with v2). With v1 the 8B model labelled nearly every call's disclaimer `not_applicable`.
- **Latency and cost.** gpt-4o-mini answers in 1.7 s (p95 2.5–3.6 s) for $0.60 per 1,000 calls with v2 (v2's longer prompt costs 14% more than v1's $0.53). The local models cost nothing per call but take 8–16 s (p95 16–44 s) on the laptop.

**Read the accuracy with the golden set's limits in mind.** There are 10 calls, so one call = 0.10. No golden call has a correctly placed disclaimer: the labels are `no` × 7 and `not_applicable` × 3, never `yes`. Answering `no` every time would score 0.70 on that field, and answering `plan_sales` every time would score 0.90 on `call_type` (9 of 10 golden calls are plan sales). Only one golden call contains objections, so the objection columns rest on that single call. The ranking below therefore weighs **which mistakes** each model makes, not just the accuracy.

## Error analysis

Every disagreement with the golden set is in `results/golden_errors.csv` (`make errors`). Five typical errors:

**1. `direction` without speaker labels (fixed by v2, with one new mistake).** On outbound calls gpt-4o-mini v1 answered `inbound` or `unknown` (direction 0.10). In 4104666105 the agent opens with "the reason I'm calling you today is because…", and in 5169932905 with "the reason of my call is to let you know that your Medicare is getting upgraded". v1 was predicted `inbound` / `unknown` for these, v2 `outbound`. The cause is that the transcript has no speakers, so the model judged "who called" by who talked most or who asked questions; the v2 opening cues fixed all five outbound-campaign calls. The new error is my own rule: v2 says a screener's warm transfer ("I have Ms. [PERSON_NAME] on the line, she is interested in…") is an inbound caller. Golden labels mark these `unknown`, because the transcript shows the transfer, not who dialled first. In 2021-08-25-15-00-51 the customer even says "Someone call me", so it's outbound, yet v2 led gpt-4o-mini to `inbound`. The dev set suggested the rule, but `LABELING.md` didn't support it, and v3 should drop it.

**2. A consent script mistaken for the CMS disclaimer (the costly error; made worse by v2).** In 5 golden calls, gpt-4o-mini v2 answered `disclaimer_before_benefits = yes`. Each time its evidence quote is something other than the disclaimer:
   - the scope-of-appointment consent: "This verbal scope of appointment allows me to discuss the different Medicare plans that are available [DRUG] your area today." (2021-08-25-15-00-51)
   - another appointment consent: "I just need to record your agreement to begin a telephone appointment to discuss these products." (2021-08-27-19-48-40)
   - the recording notice: "for your protection, we're on a recorded line." (2021-08-18-14-54-00)
   - a pitch line: "I hope you understood this call is all about your additional Medicare benefits" (5169932905)

   qwen3:14b v2 makes the same mistake on the two appointment-consent calls. The correct answer is `no` on three of these calls (plans are described and no "we do not offer every plan available in your area" statement comes first) and `not_applicable` on the other two. The cause: v2's decision order ("if benefits were described, the answer is `yes` or `no`, never `not_applicable`") forced a yes/no choice, and the prompt defines the disclaimer only by example, so the model grabbed the nearest compliance-sounding sentence. For a compliance product this is the worst error, because a false `yes` hides a violation. Fix for v3: list what is *not* the disclaimer (recording notice, scope of appointment, consent to discuss plans), and add a code check that `yes` evidence contains the disclaimer's key phrases ("every plan", "limited number of plans").

**3. A "$0 premium" pitch not counted as discussing benefits (the small model's main error).** 9312963581 is a 394-word outbound call. The screener says "I'm just helping you out to get you some extra benefits onto your Medicare card with no additional cost to you. It's gonna be [MONEY_AMOUNT] [MONEY_AMOUNT] premium now in your area", checks Part A/B and transfers the customer. No disclaimer is given, so the golden label is `no`. gpt-4o-mini (v1 and v2) and qwen3:8b (v1 and v2) answered `not_applicable`. The cause: the call is short and reads like eligibility screening before a transfer, so the models don't treat a premium amount as a plan benefit, although the prompt lists premiums. qwen3:8b makes this error on 5 of the 7 golden calls labelled `no`, even with v2's explicit order. The 8B model doesn't follow the multi-step rule; the 14B model mostly does.

**4. Equipment pitch vs plan sales.** DMEMED_rmbpo18_20211221 comes from the medical-equipment campaign: "this call is regarding for your benefits at no cost to you … some new benefits recently became available that you may qualify for … have you ever had any [MEDICAL_CONDITION]". gpt-4o-mini predicted `call_type = plan_sales` with both prompts, and then `disclaimer_before_benefits = yes`, quoting an equipment line as the disclaimer. The cause: equipment and plan pitches share the same script ("benefits at no cost", the Medicare Part A/B check), and the actual product is named only later, often masked (`[MEDICAL_PROCESS]`). The reverse also happens. Two of the three golden calls from the equipment campaign are labelled `plan_sales` in the golden set. So `call type acc (all)`, which scores against the campaign, is only a rough proxy, and its drop for gpt-4o-mini v2 (0.64 → 0.58) comes mostly from inbound-campaign calls going to `other` (2 → 4).

**5. `recording_disclosed`: `null` instead of `false`.** Outbound calls such as 9312963581 and 4104666105 start at the customer's "Hello?" and never mention recording, so the golden label is `false`. gpt-4o-mini answers `null` with both prompts (field accuracy 0.60). The prompt allows `null` when "the transcript starts mid-call", and the model can't tell that "Hello?" is the very start. qwen3:8b answers `false` and scores 0.90–1.00. The model is being over-cautious; the fix is a cue in the prompt: a transcript that begins with the customer answering the phone includes the opening.

## Production choice

**qwen3:14b with prompt v2 and `deterministic` sampling, used as a first-pass reviewer that flags calls for a human QA analyst.** The product is the disclaimer check. On that field qwen3:14b v2 misses the fewest violations: it catches 4 of the 7 golden calls labelled `no`, against 2 of 7 for gpt-4o-mini v2 and qwen3:8b v2. It never answers `yes` on a `not_applicable` call (gpt-4o-mini v2 does this twice), and it ties the best average across all fields (0.62). It runs locally, so unmasked production calls (Medicare members' health and personal data) never leave our infrastructure, and the per-call cost is $0. At p50 16 s it handles about 5,000 calls a day sequentially on one laptop, which is enough for batch QA of the previous day's calls. No model is accurate enough for automatic compliance verdicts, so a human still confirms each flag. **I would change the choice if:**
   - QA needs answers in seconds (live agent assist): switch to gpt-4o-mini (1.7 s), but only after a v3 prompt fixes its false `yes` disclaimers.
   - Volume outgrows one local machine: at ~$0.60 per 1,000 calls, a million calls a month costs about $600 in API fees, the figure to compare with the cost of extra GPUs.
   - A provider agreement covering health data (e.g. a BAA) makes sending raw transcripts acceptable.
   - A larger golden set with correctly placed disclaimers (`yes` labels) ranks the models differently. With 10 calls and no positive examples, a difference of 0.10 is one call.

## Next steps

- Prompt v3: drop the warm-transfer direction rule; list what is *not* the disclaimer; add the "Hello? = call opening" cue.
- Add a code check that `yes` disclaimer evidence contains the disclaimer's key phrases.
- Grow the golden set to 30+ calls, including calls with a correctly placed disclaimer.
